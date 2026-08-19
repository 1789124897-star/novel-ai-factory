"""TTS 路由"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.tts import TTSRequest
from app.tasks import tts_tasks

router = APIRouter(prefix="/api/tts", tags=["TTS"])


@router.post("")
async def start_tts(req: TTSRequest) -> dict:
    """启动配音合成任务"""
    if not req.text.strip():
        raise HTTPException(400, "文本不能为空")
    try:
        task_id = tts_tasks.start_synthesis(
            text=req.text.strip(),
            voice=req.voice,
            rate=req.rate,
        )
        return {"data": {"task_id": task_id}, "message": "ok"}
    except Exception as e:
        raise HTTPException(500, str(e)) from e


@router.get("/{task_id}")
async def get_tts_status(task_id: str) -> dict:
    """轮询配音任务状态"""
    state = tts_tasks.get_task_status(task_id)
    if not state:
        raise HTTPException(404, "任务不存在")
    return {"data": {"task_id": task_id, **state}, "message": "ok"}
