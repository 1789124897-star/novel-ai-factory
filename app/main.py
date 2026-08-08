#!/usr/bin/env python3
"""novel-ai-factory CLI — AI 小说→视频全流程管线。

用法：
    novel-ai-factory run --theme "仵作之死"        # 全流程
    novel-ai-factory novel --theme "铁甲怪人"       # 仅生成小说
    novel-ai-factory presets                        # 列出主题预设
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  bootstrap
# ═══════════════════════════════════════════════════════════════

def _bootstrap(theme: str = ""):
    """创建 Settings + PathConfig + 日志配置。每次 CLI 调用执行一次。"""
    from app.core.config import settings
    from app.core.logging import setup_logging
    from app.core.paths import PathConfig

    setup_logging(settings)
    paths = PathConfig.from_settings(settings, theme=theme)
    return settings, paths


# ═══════════════════════════════════════════════════════════════
#  子命令处理器
# ═══════════════════════════════════════════════════════════════

def _cmd_novel(args: argparse.Namespace) -> int:
    """``novel`` 子命令 — 编译内核 + 生成小说。"""
    from app.novel.compiler import ThemeCompiler
    from app.novel.generator import NovelGenerator
    from app.novel.prompt import NovelPrompt

    theme = args.theme or ""
    settings, paths = _bootstrap(theme)

    # 1. 编译内核
    print(f"\n{'='*60}")
    print(f"  🔮 编译叙事内核：{theme}")
    print(f"{'='*60}")
    compiler = ThemeCompiler(settings, paths)
    try:
        kernel = compiler.compile(theme)
        compiler.save_kernel(kernel, paths.kernel_file)
        print(f"  ✓ 内核已保存 → {paths.kernel_file}")
    finally:
        compiler.close()

    # 2. 生成小说
    print(f"\n{'='*60}")
    print(f"  📖 四阶段小说生成 (起·承·转·合)")
    print(f"{'='*60}")
    kernel_text = ThemeCompiler.kernel_to_prompt_text(kernel)
    prompt = NovelPrompt(theme, paths, kernel_text)
    generator = NovelGenerator(prompt, paths, settings)
    novel_text = generator.generate_novel(target_words=args.target_words)
    paths.novel_output.write_text(novel_text, encoding="utf-8")
    print(f"\n  ✅ 小说完成 — {len(novel_text)} 字 → {paths.novel_output}")
    return 0


def _cmd_tts(args: argparse.Namespace) -> int:
    """``tts`` 子命令 — 分割、合成、合并，可选混 BGM。"""
    from app.tts.engine import TTSEngine

    settings, paths = _bootstrap(args.theme or "")
    engine = TTSEngine(settings, paths)

    if args.command_tts == "generate":
        novel_path = args.novel_file or paths.novel_output
        if not Path(novel_path).exists():
            print(f"❌ 小说文件不存在：{novel_path}", file=sys.stderr)
            return 1

        print(f"\n{'='*60}")
        print(f"  🔊 TTS 语音合成")
        print(f"{'='*60}")
        text = engine.load_novel(Path(novel_path))
        segments = engine.split(text)
        if not segments:
            print("❌ 文本分割结果为空", file=sys.stderr)
            return 1
        engine.save_preview(segments)
        print(f"  分割为 {len(segments)} 个片段")

        client = engine.init_client()
        failed: list[int] = []
        for seg in segments:
            sid, stext = seg["segment_id"], seg["text"]
            print(f"  🔊 [{sid}/{len(segments)}] ", end="", flush=True)
            result = engine.synthesize(client, stext, sid)
            if result is None:
                failed.append(sid)
                print("❌")
            else:
                print("✅")

        if failed:
            paths.failed_file.write_text("\n".join(map(str, failed)), encoding="utf-8")
            print(f"\n⚠️  {len(failed)} 个片段失败 → {paths.failed_file}")
            return 1

        engine.merge(paths.merged_audio)
        print(f"\n  ✅ 音频合并完成 → {paths.merged_audio}")

    elif args.command_tts == "mix":
        print(f"\n{'='*60}")
        print(f"  🎵 BGM 混音")
        print(f"{'='*60}")
        if not paths.merged_audio.exists():
            print(f"❌ 未找到合并音频：{paths.merged_audio}", file=sys.stderr)
            return 1
        bgm = args.bgm or paths.bgm_path
        if not Path(bgm).exists():
            print(f"❌ BGM 文件不存在：{bgm}", file=sys.stderr)
            return 1
        engine.mix_bgm(paths.merged_audio, Path(bgm), paths.final_mixed_audio)
        print(f"  ✅ 混音完成 → {paths.final_mixed_audio}")

    return 0


def _cmd_srt(args: argparse.Namespace) -> int:
    """``srt`` 子命令 — TurboScribe 转录音频，转 SRT。"""
    from app.subtitle.converter import TxtToSrt
    from app.subtitle.transcriber import TurboScribeTranscriber

    settings, paths = _bootstrap(args.theme or "")

    print(f"\n{'='*60}")
    print(f"  🌐 TurboScribe 转录 + SRT 转换")
    print(f"{'='*60}")

    if not paths.merged_audio.exists():
        print("⚠️  请先运行 `tts generate` 生成 merged.mp3", file=sys.stderr)
        return 1

    with TurboScribeTranscriber(settings, paths) as ts:
        ts.transcribe(paths.merged_audio)

    converter = TxtToSrt()
    converter.convert_file(paths.crawler_unprocessed_srt, paths.crawler_cleaned_srt)
    print(f"  ✅ 字幕生成完成 → {paths.crawler_cleaned_srt}")
    return 0


def _cmd_video(args: argparse.Namespace) -> int:
    """``video`` 子命令 — 拼接片段、叠加字幕、添加水印。"""
    from app.video.pipeline import VideoPipeline
    from app.video.subtitle_renderer import SubtitleRenderer
    from app.video.watermark import Watermark

    settings, paths = _bootstrap(args.theme or "")

    if args.command_video in ("assemble", None):
        print(f"\n{'='*60}")
        print(f"  🎬 视频拼接")
        print(f"{'='*60}")
        if not paths.final_mixed_audio.exists():
            print("⚠️  请先运行 `tts mix` 生成 final_with_bgm.mp3", file=sys.stderr)
            return 1
        vp = VideoPipeline(settings, paths)
        vp.assemble(start_index=args.start_index)
        print(f"  ✅ 视频拼接完成 → {paths.video_with_bgm}")

    if args.command_video in ("subtitle", None):
        print(f"\n{'='*60}")
        print(f"  📝 字幕叠加")
        print(f"{'='*60}")
        if not paths.video_with_bgm.exists():
            print("⚠️  请先运行 `video assemble`", file=sys.stderr)
            return 1
        if not paths.crawler_cleaned_srt.exists():
            print("⚠️  请先运行 `srt`", file=sys.stderr)
            return 1
        sr = SubtitleRenderer(font_path=paths.font_path)
        sr.render(paths.video_with_bgm, paths.crawler_cleaned_srt, paths.video_with_srt)
        print(f"  ✅ 字幕添加完成 → {paths.video_with_srt}")

    if args.command_video in ("watermark", None):
        print(f"\n{'='*60}")
        print(f"  💧 水印添加")
        print(f"{'='*60}")
        if not paths.video_with_srt.exists():
            print("⚠️  请先运行 `video subtitle`", file=sys.stderr)
            return 1
        wm = Watermark(settings, paths)
        wm.apply(theme=args.theme or "")
        print(f"  ✅ 水印添加完成 → {paths.video_with_watermark}")

    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    """``run`` 子命令 — 全流程端到端，一次 bootstrap。"""
    from app.core.config import settings
    from app.core.logging import setup_logging
    from app.core.paths import PathConfig
    from app.novel.compiler import ThemeCompiler
    from app.novel.generator import NovelGenerator
    from app.novel.prompt import NovelPrompt
    from app.pipeline.stage import Stage
    from app.subtitle.converter import TxtToSrt
    from app.subtitle.transcriber import TurboScribeTranscriber
    from app.tts.engine import TTSEngine
    from app.video.pipeline import VideoPipeline
    from app.video.subtitle_renderer import SubtitleRenderer
    from app.video.watermark import Watermark

    theme = args.theme or ""

    # ── 一次 bootstrap ─────────────────────────────────────
    setup_logging(settings)
    paths = PathConfig.from_settings(settings, theme=theme)

    # ── 解析阶段 ──────────────────────────────────────────
    if args.stages:
        try:
            requested = [Stage(s.strip()) for s in args.stages.split(",")]
        except ValueError as e:
            print(f"❌ 无效阶段名: {e}", file=sys.stderr)
            print(f"   可用阶段: {', '.join(s.value for s in Stage)}", file=sys.stderr)
            return 1
        stages = requested
    else:
        stages = Stage.full_pipeline()

    skip = set(args.skip or [])
    stages = [s for s in stages if s.value not in skip]
    stage_set = set(stages)

    if not stages:
        print("⚠️  没有要执行的阶段", file=sys.stderr)
        return 0

    print(f"\n{'='*60}")
    print(f"  🚀 小说AI工厂 · 全流程管道")
    print(f"  主题: {theme}")
    print(f"  {' → '.join(s.value for s in stages)}")
    print(f"{'='*60}")

    # ════════════════════════════════════════════════════════
    #  Phase 1: Novel
    # ════════════════════════════════════════════════════════
    kernel = None

    if Stage.COMPILE in stage_set:
        print(f"\n  🔮 编译叙事内核 …")
        compiler = ThemeCompiler(settings, paths)
        try:
            kernel = compiler.compile(theme)
            compiler.save_kernel(kernel, paths.kernel_file)
            print(f"  ✓ 内核已保存 → {paths.kernel_file}")
        finally:
            compiler.close()

    if Stage.GENERATE in stage_set:
        if kernel is None:
            # 内核已在之前步骤编译，或从上次运行中读取
            if paths.kernel_file.exists():
                import json

                kernel = json.loads(paths.kernel_file.read_text(encoding="utf-8"))
            else:
                print("❌ 需要先编译叙事内核 (--stages compile)", file=sys.stderr)
                return 1

        print(f"\n  📖 四阶段小说生成 (起·承·转·合)")
        kernel_text = ThemeCompiler.kernel_to_prompt_text(kernel)
        prompt = NovelPrompt(theme, paths, kernel_text)
        generator = NovelGenerator(prompt, paths, settings)
        novel_text = generator.generate_novel()
        paths.novel_output.write_text(novel_text, encoding="utf-8")
        print(f"  ✅ 小说完成 — {len(novel_text)} 字 → {paths.novel_output}")

    # ════════════════════════════════════════════════════════
    #  Phase 2: TTS
    # ════════════════════════════════════════════════════════
    engine = TTSEngine(settings, paths)

    if Stage.TTS in stage_set:
        if not paths.novel_output.exists():
            print("❌ 需要先运行 `generate` 阶段", file=sys.stderr)
            return 1

        print(f"\n  🔊 TTS 语音合成")
        text = engine.load_novel(paths.novel_output)
        segments = engine.split(text)
        if not segments:
            print("❌ 文本分割结果为空", file=sys.stderr)
            return 1
        engine.save_preview(segments)
        print(f"  分割为 {len(segments)} 个片段")

        client = engine.init_client()
        failed: list[int] = []
        for seg in segments:
            sid, stext = seg["segment_id"], seg["text"]
            print(f"  🔊 [{sid}/{len(segments)}] ", end="", flush=True)
            result = engine.synthesize(client, stext, sid)
            if result is None:
                failed.append(sid)
                print("❌")
            else:
                print("✅")

        if failed:
            paths.failed_file.write_text("\n".join(map(str, failed)), encoding="utf-8")
            print(f"\n⚠️  {len(failed)} 个片段失败 → {paths.failed_file}")
            if Stage.MIX_BGM not in stage_set:
                return 1

        if not failed:
            engine.merge(paths.merged_audio)
            print(f"  ✅ 音频合并完成 → {paths.merged_audio}")

    if Stage.MIX_BGM in stage_set:
        if not paths.merged_audio.exists():
            print("❌ 需要先运行 `tts` 阶段生成 merged.mp3", file=sys.stderr)
            return 1
        bgm = paths.bgm_path
        if not bgm.exists():
            print(f"❌ BGM 文件不存在: {bgm}", file=sys.stderr)
            return 1
        print(f"\n  🎵 BGM 混音")
        engine.mix_bgm(paths.merged_audio, bgm, paths.final_mixed_audio)
        print(f"  ✅ 混音完成 → {paths.final_mixed_audio}")

    # ════════════════════════════════════════════════════════
    #  Phase 3: SRT
    # ════════════════════════════════════════════════════════
    if Stage.TRANSCRIBE in stage_set:
        if not paths.merged_audio.exists():
            print("❌ 需要先运行 `tts` 阶段", file=sys.stderr)
            return 1

        print(f"\n  🌐 TurboScribe 转录 + SRT 转换")
        with TurboScribeTranscriber(settings, paths) as ts:
            ts.transcribe(paths.merged_audio)
        TxtToSrt().convert_file(paths.crawler_unprocessed_srt, paths.crawler_cleaned_srt)
        print(f"  ✅ 字幕生成完成 → {paths.crawler_cleaned_srt}")

    # ════════════════════════════════════════════════════════
    #  Phase 4: Video
    # ════════════════════════════════════════════════════════
    if Stage.MAKE_VIDEO in stage_set:
        if not paths.final_mixed_audio.exists():
            print("❌ 需要先运行 `mix-bgm` 阶段", file=sys.stderr)
            return 1
        print(f"\n  🎬 视频拼接")
        VideoPipeline(settings, paths).assemble(start_index=0)
        print(f"  ✅ 视频拼接完成 → {paths.video_with_bgm}")

    if Stage.SUBTITLE in stage_set:
        if not paths.video_with_bgm.exists():
            print("❌ 需要先运行 `make-video` 阶段", file=sys.stderr)
            return 1
        if not paths.crawler_cleaned_srt.exists():
            print("❌ 需要先运行 `transcribe` 阶段", file=sys.stderr)
            return 1
        print(f"\n  📝 字幕叠加")
        SubtitleRenderer(font_path=paths.font_path).render(
            paths.video_with_bgm, paths.crawler_cleaned_srt, paths.video_with_srt
        )
        print(f"  ✅ 字幕添加完成 → {paths.video_with_srt}")

    if Stage.WATERMARK in stage_set:
        if not paths.video_with_srt.exists():
            print("❌ 需要先运行 `subtitle` 阶段", file=sys.stderr)
            return 1
        print(f"\n  💧 水印添加")
        Watermark(settings, paths).apply(theme=theme)
        print(f"  ✅ 水印添加完成 → {paths.video_with_watermark}")

    print(f"\n{'='*60}")
    print(f"  🎉 管道执行完毕！")
    print(f"{'='*60}")
    return 0


def _cmd_presets(_args: argparse.Namespace) -> int:
    """列出可用主题预设。"""
    from app.novel.presets import PRESETS

    print("\n可用主题预设：\n")
    for p in PRESETS:
        print(f"  {p.slug:20s}  {p.label}")
        if p.description:
            print(f"  {'':20s}  {p.description}")
        print(f"  {'':20s}  标签：{' · '.join(p.tags)}")
        print()
    return 0


# ═══════════════════════════════════════════════════════════════
#  parser
# ═══════════════════════════════════════════════════════════════

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="novel-ai-factory",
        description="AI 小说工厂 — 从主题到带字幕视频的全流程生成管线",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  novel-ai-factory presets                    列出主题预设
  novel-ai-factory novel -t "仵作之死"        仅生成小说
  novel-ai-factory run -t "铁甲怪人"          运行全流程
  novel-ai-factory run -t "..." --skip tts srt  跳过 TTS 和字幕
""",
    )
    subs = p.add_subparsers(dest="command")

    # ── novel ────────────────────────────────────────────────
    n = subs.add_parser("novel", help="生成小说（编译内核 + 四阶段生成）")
    n.add_argument("--theme", "-t", help="故事主题")
    n.add_argument("--target-words", type=int, default=8000, help="目标字数 (默认 8000)")

    # ── tts ──────────────────────────────────────────────────
    t = subs.add_parser("tts", help="TTS 语音合成 / 混音")
    t.add_argument("--theme", "-t", help="故事主题（用于路径解析）")
    ts = t.add_subparsers(dest="command_tts")
    tg = ts.add_parser("generate", help="合成语音并合并")
    tg.add_argument("--novel-file", type=Path, help="小说文件路径 (默认使用最新生成)")
    tm = ts.add_parser("mix", help="混音 (语音 + BGM)")
    tm.add_argument("--bgm", type=Path, help="BGM 文件路径 (默认 assets/bgm/bgm.mp3)")

    # ── srt ──────────────────────────────────────────────────
    sr = subs.add_parser("srt", help="TurboScribe 转录 + SRT 转换")
    sr.add_argument("--theme", "-t", help="故事主题（用于路径解析）")

    # ── video ────────────────────────────────────────────────
    v = subs.add_parser("video", help="视频拼接 / 字幕 / 水印")
    v.add_argument("--theme", "-t", help="故事主题（用于路径解析和水印）")
    vs = v.add_subparsers(dest="command_video")
    va = vs.add_parser("assemble", help="拼接视频片段")
    va.add_argument("--start-index", type=int, default=0, help="从第几个视频开始 (0=第一个)")
    vs.add_parser("subtitle", help="叠加字幕")
    vs.add_parser("watermark", help="添加水印")

    # ── run ──────────────────────────────────────────────────
    r = subs.add_parser("run", help="运行完整管道")
    r.add_argument("--theme", "-t", help="故事主题")
    r.add_argument("--stages", help="指定阶段，逗号分隔 (默认全部)")
    r.add_argument("--skip", nargs="*", help="跳过的阶段名")

    # ── presets ──────────────────────────────────────────────
    subs.add_parser("presets", help="列出主题预设")

    return p


# ═══════════════════════════════════════════════════════════════
#  入口
# ═══════════════════════════════════════════════════════════════

_HANDLERS = {
    "novel": _cmd_novel,
    "tts": _cmd_tts,
    "srt": _cmd_srt,
    "video": _cmd_video,
    "run": _cmd_run,
    "presets": _cmd_presets,
}


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    handler = _HANDLERS.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    try:
        return handler(args)
    except KeyboardInterrupt:
        print("\n👋 已取消")
        return 130
    except Exception:
        logger.exception("'%s' 命令发生未处理异常", args.command)
        return 1


if __name__ == "__main__":
    sys.exit(main())
