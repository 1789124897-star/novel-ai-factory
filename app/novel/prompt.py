"""分阶段 prompt 构建器 — 以叙事内核为锚点组装提示词。"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.config import Settings
    from ..core.paths import PathConfig

logger = logging.getLogger(__name__)


class NovelPrompt:
    """组装每阶段 prompt，以不可变叙事内核为锚点。

    内核在每阶段均先于基础 prompt 注入，确保 LLM 不偏离原始故事 DNA。
    """

    def __init__(self, theme: str, paths: "PathConfig", kernel: str):
        self.theme = theme
        self.kernel = kernel
        self._base = self._load_base_prompt(paths)

    # ── 公开 API ───────────────────────────────────────

    def get_stage_prompt(
        self,
        stage_info: dict,
        previous_summary: str = "",
        current_content: str = "",
    ) -> str:
        """构建单阶段完整 prompt。

        Args:
            stage_info: dict，包含 ``name``、``chapter_range``、``word_hint``、``task``。
            previous_summary: 前一阶段的桥接摘要。
            current_content: 本阶段已有文本（用于重试/续写轮次）。

        Returns:
            组装完成的 prompt 字符串，可直接发送给 LLM。
        """
        word_range = stage_info["word_hint"]
        prompt = (
            f"【不可违背的叙事内核锚点】\n{self.kernel}\n\n"
            f"所有情节、人物动机、预言、核心事件、信物、空间异常等必须严格与以上内核一致，"
            f"不得任何改动或偏离。\n\n"
            f"{self._base.format(theme=self.theme)}\n\n"
            f"【当前写作阶段】{stage_info['name']}\n"
            f"【章节范围】{stage_info['chapter_range']}\n"
            f"【本阶段严格字数要求】必须控制在{word_range}字（纯中文字符，不计标点空格）。\n"
            f"【核心任务】{stage_info['task']}\n\n"
        )

        if previous_summary:
            prompt += f"【前情摘要】\n{previous_summary}\n\n"

        if current_content:
            prompt += (
                f"【已生成内容（请无缝接续）】\n{current_content}\n\n"
                f"请继续本阶段写作，从以上内容自然接续，扩展细节、心理描写或环境描写，"
                f"直到本阶段总字数达到{word_range}的要求。\n"
            )
        else:
            prompt += "请开始本阶段写作。\n"

        prompt += (
            "\n严格要求：\n"
            "- 直接输出小说正文，不要任何解释、说明、章节标题或统计。\n"
            "- 保持文学性、压抑氛围、不可靠叙事。\n"
            "- 结尾不要强行收束，为后续阶段留余地（除非是最终阶段）。\n"
            "- 必须满足字数硬性要求！\n"
        )
        return prompt

    # ── 内部方法 ───────────────────────────────────────

    @staticmethod
    def _load_base_prompt(paths: "PathConfig") -> str:
        prompt_path: Path = paths.theme_novel_prompt
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt 文件未找到: {prompt_path}")
        content = prompt_path.read_text(encoding="utf-8").strip()
        if not content:
            raise ValueError(f"Prompt 文件为空: {prompt_path}")
        return content
