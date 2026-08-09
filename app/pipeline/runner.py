"""管线运行器 — 从 CLI 抽出的逻辑，供 web/server 使用，支持进度回调。"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Optional

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.paths import PathConfig
from app.services import novel_service
from app.services.novel_gen_service import NovelGenerator
from app.services.novel_gen_service import NovelPrompt

logger = logging.getLogger(__name__)

STAGES = [
    (0.00, 0.40, "compile", "编译叙事内核"),
    (0.40, 1.00, "generate", "四阶段小说生成"),
]


class PipelineRunner:
    """运行小说生成全流程管线，支持进度回调。

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
            ``{theme, novel_path}``
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
            data = novel_service.compile_kernel(theme)
            kernel = data["kernel"]
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

            prompt = NovelPrompt(theme, paths, kernel)
            generator = NovelGenerator(prompt, paths, settings)

            # 用生成器内部的 4 阶段细分进度
            gen_stages = ["起", "承", "转", "合"]
            original_generate = generator.generate_novel

            def generate_with_progress():
                # 猴子补丁 _single_generate 以报告子阶段进度
                original_single = generator._single_generate
                stage_idx = [0]

                def patched_single(prompt_text, max_retries=3):
                    stage_name = gen_stages[min(stage_idx[0], 3)]
                    sub_pct = gen_start + gen_range * (stage_idx[0] / len(gen_stages))
                    report(sub_pct, f"生成中：{stage_name}")
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

        report(1.0, "完成")

        # 绝对路径 → output 相对 URL
        output_root = paths.output.parent
        for key in list(result):
            if key.endswith("_path") and result[key]:
                try:
                    relative_path = Path(result[key]).relative_to(output_root)
                    result[key] = "/" + str(relative_path).replace("\\", "/")
                except ValueError:
                    pass

        return result
