"""分阶段小说生成服务 — prompt 构建 + 四阶段生成引擎 + 异步任务调度。

核心算法：
1. 以叙事内核为锚点，注入基础 prompt 模板，组装每阶段提示词。
2. 每阶段调用 LLM 一次，传入所有已生成的前文作为上下文。
3. 后台线程运行，通过回调实时更新任务状态，前端轮询获取进度。
"""

import logging
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any, Optional

import requests

from app.core.config import settings, Settings
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
    "2. 必须使用标准标点符号，禁止无标点长句。每个句子必须以句号、问号或感叹号结尾。"
    "长句内部需用逗号分隔意群，确保句子结构清晰，适合朗读。\n"
    "   错误示例：'我推开门走进房间看见她坐在那里'\n"
    "   正确示例：'我推开门，走进房间，看见她坐在那里。'\n"
    "3. 你的目标是详细扩写细节。如果内容太短，请增加环境描写和感官细节，严禁跳过剧情。\n"
    "4. 必须使用标准简体中文，严禁繁体。"
)


# ── Prompt 构建器 ────────────────────────────────────────────

class NovelPrompt:
    """组装每阶段 prompt，以不可变叙事内核为锚点。

    内核在每阶段均先于基础 prompt 注入，确保 LLM 不偏离原始故事 DNA。
    """

    def __init__(self, theme: str, paths: PathConfig, kernel: str):
        self.theme = theme
        self.kernel_text = kernel
        self._base = self._load_base_prompt(paths)

    def get_stage_prompt(
        self,
        stage_info: dict,
        previous_full_text: str = "",
    ) -> str:
        """构建单阶段完整 prompt。

        Args:
            stage_info: dict，包含 ``name``、``chapter_range``、``word_hint``、``task``。
            previous_full_text: 之前所有阶段的小说全文，用于上下文衔接。
        """
        word_range = stage_info["word_hint"]
        prompt = (
            f"【不可违背的叙事内核锚点】\n{self.kernel_text}\n\n"
            f"所有情节、人物动机、预言、核心事件、信物、空间异常等必须严格与以上内核一致，"
            f"不得任何改动或偏离。\n\n"
            f"{self._base.format(theme=self.theme)}\n\n"
            f"【当前写作阶段】{stage_info['name']}\n"
            f"【章节范围】{stage_info['chapter_range']}\n"
            f"【本阶段严格字数要求】必须控制在{word_range}字（纯中文字符，不计标点空格）。\n"
            f"【核心任务】{stage_info['task']}\n\n"
        )

        if previous_full_text:
            prompt += (
                f"【已生成的小说全文】\n{previous_full_text}\n\n"
                f"请以上文为基础无缝续写本阶段。注意回收前文埋下的伏笔，"
                f"保持人物性格、对白风格和叙事节奏一致。\n"
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

    def _api_post(self, payload: dict) -> dict:
        resp = requests.post(
            self.settings.DEEPSEEK_BASE_URL,
            headers={
                "Authorization": f"Bearer {self.settings.DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=180,
        )
        resp.raise_for_status()
        return resp.json()

    def _single_generate(self, prompt_text: str, max_retries: int = 3) -> str:
        """调用 LLM API，带指数退避重试。每次独立请求，不携带历史。"""
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
                data = self._api_post(payload)
                return data["choices"][0]["message"]["content"].strip()
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
        """运行完整四阶段生成流程。

        Args:
            target_words: 近似总字数目标（传递到 prompt 中作为提示）。
            on_stage_complete: 每阶段完成后的回调 (stage_name, content)。
        """
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


# ── 异步任务管理 ─────────────────────────────────────────────

# 内存任务存储（生产环境改用 Redis）
_tasks: dict[str, dict] = {}
_lock = threading.Lock()


def start_generation(theme: str, kernel: str, target_words: int = 8000) -> str:
    """启动后台小说生成任务，返回 task_id。"""
    task_id = str(uuid.uuid4())[:8]
    _tasks[task_id] = {
        "status": "running",
        "current_stage": "起",
        "stages": {},
        "error": None,
    }

    thread = threading.Thread(
        target=_run_generation, args=(task_id, theme, kernel, target_words), daemon=True
    )
    thread.start()
    logger.info("小说生成任务已启动 task_id=%s theme=%s", task_id, theme)
    return task_id


def get_task_status(task_id: str) -> Optional[dict]:
    """查询任务状态。"""
    return _tasks.get(task_id)


def _run_generation(task_id: str, theme: str, kernel: str, target_words: int) -> None:
    """后台线程：跑四阶段生成，每完成一个阶段实时更新状态。"""
    def on_stage(name: str, content: str) -> None:
        with _lock:
            task = _tasks.get(task_id)
            if task:
                task["current_stage"] = name
                task["stages"][name] = content
        logger.info("阶段 [%s] 完成，字数=%d", name, len(content))

    try:
        paths = PathConfig.from_settings(settings, theme=theme)
        prompt = NovelPrompt(theme, paths, kernel)
        generator = NovelGenerator(prompt, paths, settings)
        generator.generate_novel(
            target_words=target_words,
            on_stage_complete=on_stage,
        )

        with _lock:
            if task_id in _tasks:
                _tasks[task_id]["status"] = "done"
    except Exception as e:
        logger.exception("小说生成失败 task_id=%s", task_id)
        with _lock:
            if task_id in _tasks:
                _tasks[task_id]["status"] = "error"
                _tasks[task_id]["error"] = str(e)
