"""分阶段小说生成器 — 内置重试和续写。

核心算法：

1. 将小说分为四阶段（起-承-转-合）。
2. 每阶段调用 LLM。若输出低于最低字数目标，循环最多 3 次，将已有内容作为上下文喂回（续写）。
3. 每阶段结束后生成 ~200 字桥接摘要，供下一阶段保持连贯。
"""

import json
import logging
import re
import time
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from ..core.config import Settings
    from ..core.paths import PathConfig
    from .prompt import NovelPrompt

logger = logging.getLogger(__name__)

# ── 阶段定义 ──────────────────────────────────────────

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
    "2. 必须使用标准标点符号，禁止无标点长句。每个句子必须以句号、问号或感叹号结尾。"
    "长句内部需用逗号分隔意群，确保句子结构清晰，适合朗读。\n"
    "   错误示例：“我推开门走进房间看见她坐在那里”\n"
    "   正确示例：“我推开门，走进房间，看见她坐在那里。”\n"
    "3. 你的目标是详细扩写细节。如果内容太短，请增加环境描写和感官细节，严禁跳过剧情。\n"
    "4. 必须使用标准简体中文，严禁繁体。"
)


class NovelGenerator:
    """编排四阶段小说生成，带自动重试续写。"""

    MAX_CONTINUE_ROUNDS = 3

    def __init__(
        self,
        prompt: "NovelPrompt",
        paths: "PathConfig",
        settings: "Settings",
    ):
        self.settings = settings
        self.prompt = prompt
        self.paths = paths
        self._session = requests.Session()
        self.history_messages: list[dict] = []
        self._load_history()

    # ── 历史持久化 ─────────────────────────────────────

    def _load_history(self) -> None:
        hf = self.paths.history_file
        if hf.exists():
            self.history_messages = json.loads(hf.read_text(encoding="utf-8"))
            logger.info("已加载 %d 条历史消息", len(self.history_messages))

    def _save_history(self) -> None:
        self.paths.history_file.write_text(
            json.dumps(self.history_messages, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ── HTTP 工具 ──────────────────────────────────────

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.settings.DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        }

    def _build_payload(self, user_content: str) -> dict:
        messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
        messages.extend(self.history_messages)
        messages.append({"role": "user", "content": user_content})
        return {
            "model": self.settings.DEEPSEEK_MODEL,
            "messages": messages,
            "temperature": self.settings.DEEPSEEK_TEMPERATURE,
            "top_p": self.settings.DEEPSEEK_TOP_P,
            "max_tokens": self.settings.DEEPSEEK_MAX_TOKENS,
            "presence_penalty": self.settings.DEEPSEEK_PRESENCE_PENALTY,
            "frequency_penalty": self.settings.DEEPSEEK_FREQUENCY_PENALTY,
            "stream": False,
        }

    def _single_generate(self, prompt_text: str, max_retries: int = 3) -> str:
        """调用 LLM API，带指数退避重试。"""
        for attempt in range(max_retries):
            try:
                payload = self._build_payload(prompt_text)
                resp = self._session.post(
                    self.settings.DEEPSEEK_BASE_URL,
                    headers=self._headers,
                    json=payload,
                    timeout=180,
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"].strip()

                self.history_messages.append({"role": "user", "content": prompt_text})
                self.history_messages.append({"role": "assistant", "content": content})
                self._save_history()
                return content
            except Exception:
                logger.warning("LLM 调用第 %d/%d 次失败", attempt + 1, max_retries)
                if attempt < max_retries - 1:
                    time.sleep(2**attempt)
                else:
                    raise

        raise RuntimeError(f"LLM 调用 {max_retries} 次后仍失败")

    # ── 摘要器 ─────────────────────────────────────────

    def _generate_summary(self, text: str) -> str:
        """生成片段结尾的桥接摘要（基于文本最后 3000 字）。"""
        summary_prompt = (
            "请用不超过200字，总结以下小说片段的结尾状态：\n"
            "1. 主要人物的心理状态\n"
            "2. 当前的悬念和未解之谜\n"
            "3. 空间环境和信物的异常表现\n"
            "4. 故事即将发展的方向\n\n"
            "请用简洁、连贯的语言总结，直接输出摘要内容。\n\n"
            f"文本片段：\n{text[-3000:]}"
        )
        return self._single_generate(summary_prompt, max_retries=2).strip()

    # ── 主流程 ─────────────────────────────────────────

    def generate_novel(self, target_words: int = 8000) -> str:
        """运行完整四阶段生成流程。

        Args:
            target_words: 近似总字数目标。用于按比例缩放每阶段字数提示。
                实际输出约在 ``target_words ± 15%`` 范围内。

        Returns:
            完整小说文本。
        """
        # 相对于默认 8000 字目标计算缩放因子
        scale = max(0.5, min(2.0, target_words / 8000))
        logger.info(
            "开始分阶段小说生成（目标 ~%d 字，缩放比例 %.2f）",
            target_words,
            scale,
        )

        full_content = ""
        previous_summary = ""

        for idx, stage in enumerate(STAGES, 1):
            logger.info("━ 第 %d 阶段：【%s】", idx, stage["name"])
            word_range = stage["word_hint"]
            # 兼容全角破折号 (U+2013) 和 ASCII 连字符
            parts = re.split(r"[–\-]", word_range)
            min_words = int(int(parts[0]) * scale)
            max_words = int(int(parts[1]) * scale)

            stage_content = ""
            for round_idx in range(self.MAX_CONTINUE_ROUNDS + 1):
                if round_idx == 0:
                    stage_prompt = self.prompt.get_stage_prompt(
                        stage, previous_summary
                    )
                else:
                    stage_prompt = self.prompt.get_stage_prompt(
                        stage, previous_summary, stage_content
                    )

                part = self._single_generate(stage_prompt)
                stage_content += "\n\n" + part if stage_content else part
                current_len = len(stage_content)
                logger.info(
                    "  第 %d 轮 → %d 字 (目标 %d–%d)",
                    round_idx + 1,
                    current_len,
                    min_words,
                    max_words,
                )
                if current_len >= min_words:
                    break

            full_content += stage_content + "\n\n"
            self.paths.part_file(idx).write_text(stage_content, encoding="utf-8")
            previous_summary = self._generate_summary(stage_content)
            logger.info("  第 %d 阶段完成 — %d 字", idx, len(stage_content))

        logger.info("所有阶段完成 — 共 %d 字", len(full_content))
        return full_content
