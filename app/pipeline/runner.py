"""管线运行器 — 从 CLI 抽出的逻辑，供 web/server 使用，支持进度回调。"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Optional

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.paths import PathConfig
from app.novel.compiler import ThemeCompiler
from app.novel.generator import NovelGenerator
from app.novel.prompt import NovelPrompt
from app.subtitle.converter import TxtToSrt
from app.subtitle.transcriber import TurboScribeTranscriber
from app.tts.engine import TTSEngine
from app.video.pipeline import VideoPipeline
from app.video.subtitle_renderer import SubtitleRenderer
from app.video.watermark import Watermark

logger = logging.getLogger(__name__)

# 实际共 12 个原子步骤（编译 + 生成 4 段 + tts + 混音 + 转录 + 视频拼接 + 字幕 + 水印）
# 对上层暴露为 8 个主阶段，内部细分进度
STAGES = [
    (0.00, 0.10, "compile", "编译叙事内核"),
    (0.10, 0.30, "generate", "四阶段小说生成"),
    (0.30, 0.42, "tts", "TTS 语音合成"),
    (0.42, 0.48, "mix-bgm", "BGM 混音"),
    (0.48, 0.58, "transcribe", "字幕转录"),
    (0.58, 0.70, "make-video", "视频拼接"),
    (0.70, 0.85, "subtitle", "字幕叠加"),
    (0.85, 1.00, "watermark", "水印"),
]


class PipelineRunner:
    """运行小说→视频全流程管线，支持进度回调。

    用法::

        runner = PipelineRunner()
        result = runner.run("仵作之死", target_words=8000, on_progress=lambda p, s: print(p, s))
    """

    def run(
        self,
        theme: str,
        target_words: int = 8000,
        *,
        on_progress: Optional[Callable[[float, str], None]] = None,
        skip: Optional[list[str]] = None,
    ) -> dict:
        """运行全流程并返回产物路径。

        Args:
            theme: 故事主题字符串。
            target_words: 小说目标字数。
            on_progress: ``(pct: float, stage: str)`` 进度回调。
            skip: 要跳过的阶段名列表。

        Returns:
            ``{theme, novel_path, audio_path, video_path, ...}``
        """
        skip_set = set(skip or [])

        def report(pct: float, stage: str):
            logger.info(f"[{pct*100:.0f}%] {stage}")
            if on_progress:
                on_progress(pct, stage)

        # ── 初始化 ─────────────────────────────────────────
        setup_logging(settings)
        paths = PathConfig.from_settings(settings, theme=theme)

        report(0.0, f"开始：{theme}")

        kernel = None
        result: dict = {"theme": theme}

        # ── 1. 编译内核 ────────────────────────────────────
        if "compile" not in skip_set:
            report(STAGES[0][0], STAGES[0][2])
            compiler = ThemeCompiler(settings, paths)
            try:
                kernel = compiler.compile(theme)
                compiler.save_kernel(kernel, paths.kernel_file)
            finally:
                compiler.close()
            report(STAGES[0][1] - 0.01, STAGES[0][2])

        # ── 2. 生成小说（四阶段）──────────────────────────
        if "generate" not in skip_set:
            if kernel is None and paths.kernel_file.exists():
                import json

                kernel = json.loads(paths.kernel_file.read_text(encoding="utf-8"))

            if kernel is None:
                raise RuntimeError("需要先编译叙事内核")

            gen_start, gen_end = STAGES[1][0], STAGES[1][1]
            gen_range = gen_end - gen_start
            report(gen_start, "generate")

            kernel_text = ThemeCompiler.kernel_to_prompt_text(kernel)
            prompt = NovelPrompt(theme, paths, kernel_text)
            generator = NovelGenerator(prompt, paths, settings)

            # 用生成器内部的 4 阶段细分进度
            gen_stages = ["起", "承", "转", "合"]
            original_generate = generator.generate_novel

            def generate_with_progress():
                # 猴子补丁 _single_generate 以报告子阶段进度
                original_single = generator._single_generate
                stage_idx = [0]

                def patched_single(prompt_text, max_retries=3):
                    sname = gen_stages[min(stage_idx[0], 3)]
                    sub_pct = gen_start + gen_range * (stage_idx[0] / len(gen_stages))
                    report(sub_pct, f"生成中：{sname}")
                    result_text = original_single(prompt_text, max_retries)
                    stage_idx[0] += 1
                    return result_text

                generator._single_generate = patched_single
                try:
                    return original_generate(target_words=target_words)
                finally:
                    generator._single_generate = original_single

            novel_text = generate_with_progress()
            paths.novel_output.write_text(novel_text, encoding="utf-8")
            report(gen_end - 0.01, "generate")
            result["novel_path"] = str(paths.novel_output)

        # ── 3. TTS 合成 ─────────────────────────────────────
        if "tts" not in skip_set:
            report(STAGES[2][0], "tts")
            engine = TTSEngine(settings, paths)
            text = engine.load_novel(paths.novel_output)
            segments = engine.split(text)
            engine.save_preview(segments)

            tts_start, tts_end = STAGES[2][0], STAGES[2][1]
            tts_range = tts_end - tts_start
            client = engine.init_client()
            failed: list[int] = []
            total_segs = len(segments)
            for seg in segments:
                sid, stext = seg["segment_id"], seg["text"]
                seg_pct = tts_start + tts_range * (sid / total_segs)
                report(seg_pct, f"TTS [{sid}/{total_segs}]")
                result_path = engine.synthesize(client, stext, sid)
                if result_path is None:
                    failed.append(sid)

            if failed:
                paths.failed_file.write_text("\n".join(map(str, failed)), encoding="utf-8")
                raise RuntimeError(f"TTS 失败：{len(failed)} 个片段")

            engine.merge(paths.merged_audio)
            report(tts_end - 0.01, "tts")
            result["audio_path"] = str(paths.merged_audio)

        # ── 4. BGM 混音 ─────────────────────────────────────
        if "mix-bgm" not in skip_set:
            report(STAGES[3][0], "mix-bgm")
            engine = TTSEngine(settings, paths)
            bgm = paths.bgm_path
            if bgm.exists():
                engine.mix_bgm(paths.merged_audio, bgm, paths.final_mixed_audio)
            else:
                logger.warning("BGM 文件不存在，跳过混音: %s", bgm)
            report(STAGES[3][1] - 0.01, "mix-bgm")
            result["mixed_audio_path"] = str(paths.final_mixed_audio)

        # ── 5. 字幕转录 ─────────────────────────────────────
        if "transcribe" not in skip_set:
            report(STAGES[4][0], "transcribe")
            trans_start, trans_end = STAGES[4][0], STAGES[4][1]
            report(trans_start + 0.03, "TurboScribe 上传转录中...")
            with TurboScribeTranscriber(settings, paths) as ts:
                ts.transcribe(paths.merged_audio)
            report(trans_start + 0.06, "生成 SRT...")
            TxtToSrt().convert_file(paths.crawler_unprocessed_srt, paths.crawler_cleaned_srt)
            report(trans_end - 0.01, "transcribe")
            result["srt_path"] = str(paths.crawler_cleaned_srt)

        # ── 6. 视频拼接 ─────────────────────────────────────
        if "make-video" not in skip_set:
            report(STAGES[5][0], "make-video")
            VideoPipeline(settings, paths).assemble(start_index=0)
            report(STAGES[5][1] - 0.01, "make-video")
            result["video_raw_path"] = str(paths.video_with_bgm)

        # ── 7. 字幕叠加 ─────────────────────────────────────
        if "subtitle" not in skip_set:
            report(STAGES[6][0], "subtitle")
            SubtitleRenderer(font_path=paths.font_path).render(
                paths.video_with_bgm, paths.crawler_cleaned_srt, paths.video_with_srt
            )
            report(STAGES[6][1] - 0.01, "subtitle")
            result["video_srt_path"] = str(paths.video_with_srt)

        # ── 8. 水印添加 ─────────────────────────────────────
        if "watermark" not in skip_set:
            report(STAGES[7][0], "watermark")
            Watermark(settings, paths).apply(theme=theme)
            report(1.0, "watermark")
            result["video_final_path"] = str(paths.video_with_watermark)

        report(1.0, "完成")

        # 绝对路径 → output 相对 URL
        output_root = paths.output.parent
        for key in list(result):
            if key.endswith("_path") and result[key]:
                try:
                    rel = Path(result[key]).relative_to(output_root)
                    result[key] = "/" + str(rel).replace("\\", "/")
                except ValueError:
                    pass

        return result
