"""分阶段小说生成服务 — prompt 构建 + 四阶段生成引擎。

核心算法：
1. 以叙事内核为锚点，注入基础 prompt 模板，组装每阶段提示词。
2. 每阶段调用 LLM 一次，传入所有已生成的前文作为上下文。
"""

import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Optional

import requests

from app.core.config import Settings
from app.core.paths import PathConfig

logger = logging.getLogger(__name__)

# ── 阶段定义 ─────────────────────────────────────────────────

STAGES = [
    {
        "name": "起",
        "chapter_range": "第1–2章",
        "word_hint": "1400–1600",
        "task": "氛围建立、预言出现、空间首次异常、信物登场、不可靠叙事启动",
    },
    {
        "name": "承",
        "chapter_range": "第3–6章",
        "word_hint": "2800–3000",
        "task": "迷恋滋生、自我欺骗、双男主介入、线索增殖但不解释",
    },
    {
        "name": "转",
        "chapter_range": "第7–9章",
        "word_hint": "2000–2200",
        "task": "偏执爆发、认知崩塌、局部真相拼接、关键反转",
    },
    {
        "name": "合",
        "chapter_range": "第10–11章",
        "word_hint": "1400–1600",
        "task": "同化完成、双男主退场、新闯入者、宿命闭环",
    },
]

_SYSTEM_PROMPT = (
    "你是一位极其严谨的长篇小说家。你的写作必须遵守以下【格式红线】，否则将被判定为废稿：\n"
    "1. 全文严禁使用任何形式的圆括号（）或方括号[]。所有心理活动必须直接书写，禁止标注。\n"
    "2. 必须使用标准标点符号。每个句子必须以句号、问号或感叹号结尾。"
    "句内用逗号分隔意群，确保句子结构清晰，适合朗读。\n"
    "   错误示例：'我推开门走进房间看见她坐在那里'\n"
    "正确示例：'我推开门，走进房间。看见她坐在那里。'\n"
    "3. 逗号子句≤10字，整句≤15字，以句号/问号/感叹号收尾。\n"
    "4. 必须使用标准简体中文，严禁繁体。"
)


# ── Prompt 构建器 ────────────────────────────────────────────

class NovelPrompt:
    """组装每阶段 prompt，以不可变叙事内核为锚点。"""

    def __init__(self, theme: str, paths: PathConfig, kernel: str):
        self.theme = theme
        self.kernel_text = kernel
        self._base = self._load_base_prompt(paths)

    def get_stage_prompt(
        self,
        stage_info: dict,
        previous_full_text: str = "",
    ) -> str:
        """构建单阶段完整 prompt。"""
        prompt_parts = [
            f"【不可违背的叙事内核锚点】\n{self.kernel_text}",
            "所有情节、人物动机、预言、核心事件、信物、空间异常等必须严格与以上内核一致，不得任何改动或偏离。",
            self._base.format(theme=self.theme),
            f"【当前写作阶段】{stage_info['name']}",
            f"【章节范围】{stage_info['chapter_range']}",
            f"【本阶段严格字数要求】必须控制在{stage_info['word_hint']}字（纯中文字符，不计标点空格）。",
            f"【核心任务】{stage_info['task']}",
        ]

        if previous_full_text:
            prompt_parts += [
                f"【已生成的小说全文】\n{previous_full_text}",
                "请以上文为基础无缝续写本阶段。注意回收前文埋下的伏笔，保持人物性格、对白风格和叙事节奏一致。",
            ]
        else:
            prompt_parts.append("请开始本阶段写作。")

        prompt_parts.append(
            "严格要求：\n"
            "- 直接输出小说正文，不要任何解释、说明、章节标题或统计。\n"
            "- 保持文学性、压抑氛围、不可靠叙事。\n"
            "- 结尾不要强行收束，为后续阶段留余地（除非是最终阶段）。\n"
            "- 必须满足字数硬性要求！"
        )
        return "\n\n".join(prompt_parts)

    @staticmethod
    def _load_base_prompt(paths: PathConfig) -> str:
        prompt_path: Path = paths.theme_novel_prompt
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt 文件未找到: {prompt_path}")
        content = prompt_path.read_text(encoding="utf-8").strip()
        if not content:
            raise ValueError(f"Prompt 文件为空: {prompt_path}")
        return content


# ── 生成引擎 ─────────────────────────────────────────────────

class NovelGenerator:
    """编排四阶段小说生成。"""

    def __init__(
        self,
        prompt: NovelPrompt,
        paths: PathConfig,
        settings: Settings,
    ):
        self.settings = settings
        self.prompt = prompt
        self.paths = paths

    def _single_generate(self, prompt_text: str, max_retries: int = 3) -> str:

        for attempt in range(max_retries):
            try:
                payload = {
                    "model": self.settings.DEEPSEEK_MODEL,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": prompt_text},
                    ],
                    "temperature": self.settings.DEEPSEEK_TEMPERATURE,
                    "max_tokens": self.settings.DEEPSEEK_MAX_TOKENS,
                }
                response = requests.post(
                    self.settings.DEEPSEEK_BASE_URL,
                    headers={
                        "Authorization": f"Bearer {self.settings.DEEPSEEK_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=180,
                )
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"].strip()
            except Exception:
                logger.warning("LLM 调用第 %d/%d 次失败", attempt + 1, max_retries)
                if attempt < max_retries - 1:
                    time.sleep(2**attempt)
                else:
                    raise

        raise RuntimeError(f"LLM 调用 {max_retries} 次后仍失败")

    def generate_novel(
        self,
        target_words: int = 8000,
        on_stage_complete: Optional[Callable[[str, str], None]] = None,
    ) -> str:
        """完整四阶段生成流程。"""

        logger.info("开始分阶段小说生成（目标 ~%d 字）", target_words)

        full_content = ""

        for idx, stage in enumerate(STAGES, 1):
            logger.info("━ 第 %d 阶段：【%s】", idx, stage["name"])

            stage_prompt = self.prompt.get_stage_prompt(stage, full_content)
            stage_content = self._single_generate(stage_prompt)

            full_content += stage_content + "\n\n"
            self.paths.part_file(idx).write_text(stage_content, encoding="utf-8")
            if on_stage_complete:
                on_stage_complete(stage["name"], stage_content)
            logger.info("  完成 — %d 字", len(stage_content))

        logger.info("所有阶段完成 — 共 %d 字", len(full_content))
        return full_content
