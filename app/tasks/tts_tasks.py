"""TTS 语音合成 — 异步任务调度"""

import asyncio
import logging
from typing import Optional

from app.services.task_manager import TaskManager
from app.services.tts_service import TTSService

logger = logging.getLogger(__name__)

_task_manager = TaskManager()


def start_synthesis(text: str, voice: str, rate: str) -> str:
    """启动后台配音合成，返回 task_id。"""
    task_id = _task_manager.start(_do_synthesis, text, voice, rate)
    logger.info("TTS 任务已启动 task_id=%s", task_id)
    return task_id


def get_task_status(task_id: str) -> Optional[dict]:
    """查询任务状态。"""
    return _task_manager.get(task_id)


def _do_synthesis(task_id: str, text: str, voice: str, rate: str) -> None:
    """后台执行 TTS 合成，完成后将结果写入任务状态。"""
    result = asyncio.run(TTSService.synthesize(task_id, text, voice, rate))
    _task_manager.update(task_id, **result)
