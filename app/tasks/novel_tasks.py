"""叙事内核编译 — 异步任务调度"""

import logging

from app.services.novel_service import compile_kernel
from app.services.task_manager import TaskManager

logger = logging.getLogger(__name__)

_task_manager = TaskManager()


def start_compile(theme: str) -> str:
    """启动后台内核编译任务，返回 task_id。"""
    task_id = _task_manager.start(_do_compile, theme)
    logger.info("内核编译任务已启动 task_id=%s theme=%s", task_id, theme)
    return task_id


def get_compile_status(task_id: str) -> Optional[dict]:
    """查询编译任务状态。"""
    return _task_manager.get(task_id)


def _do_compile(task_id: str, theme: str) -> None:
    """后台执行内核编译，完成后将结果写入任务状态。"""
    data = compile_kernel(theme)
    _task_manager.update(task_id, **data)
