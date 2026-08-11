"""小说生成 — 异步任务调度"""

import logging
from typing import Optional

from app.core.config import settings
from app.core.paths import PathConfig
from app.services.novel_gen_service import NovelPrompt, NovelGenerator
from app.services.task_manager import TaskManager

logger = logging.getLogger(__name__)

_task_manager = TaskManager()


def start_generation(
    theme: str,
    kernel: str,
    target_words: int = 8000,
    custom_prompt: Optional[str] = None,
) -> str:
    """启动后台小说生成任务，返回 task_id。"""
    task_id = _task_manager.start(
        _do_generation,
        theme,
        kernel,
        target_words,
        custom_prompt,
    )
    logger.info("小说生成任务已启动 task_id=%s theme=%s target=%d", task_id, theme, target_words)
    return task_id


def get_task_status(task_id: str) -> Optional[dict]:
    """查询任务状态。"""
    return _task_manager.get(task_id)


def _do_generation(
    task_id: str,
    theme: str,
    kernel: str,
    target_words: int,
    custom_prompt: Optional[str],
) -> None:
    """后台执行四阶段小说生成，每阶段完成实时更新状态。"""
    completed: dict[str, str] = {}

    _after = {"起": "承", "承": "转", "转": "合", "合": "完成"}

    def on_stage(name: str, content: str) -> None:
        completed[name] = content
        _task_manager.update(task_id, current_stage=_after[name], stages=dict(completed))
        logger.info("阶段 [%s] 完成，字数=%d", name, len(content))

    _task_manager.update(task_id, current_stage="起")

    paths = PathConfig.from_settings(settings, theme=theme)
    prompt = NovelPrompt(theme, paths, kernel, custom_prompt=custom_prompt)
    generator = NovelGenerator(prompt, paths, settings)
    generator.generate_novel(
        target_words=target_words,
        on_stage_complete=on_stage,
    )
