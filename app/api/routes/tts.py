"""TTS 路由"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import tts_service

router = APIRouter(prefix="/api/tts", tags=["TTS"])


class TTSRequest(BaseModel):
    text: str
    voice: str = ""
    rate: str = ""


@router.post("")
async def start_tts(req: TTSRequest) -> dict:
    """启动配音合成任务"""
    if not req.text.strip():
        raise HTTPException(400, "文本不能为空")
    try:
        task_id = tts_service.start_synthesis(
            text=req.text.strip(),
            voice=req.voice,
            rate=req.rate,
        )
        return {"data": {"task_id": task_id}, "message": "ok"}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/{task_id}")
async def get_tts_status(task_id: str) -> dict:
    """轮询配音任务状态"""
    state = tts_service.get_task_status(task_id)
    if not state:
        raise HTTPException(404, "任务不存在")
    return {"data": {"task_id": task_id, **state}, "message": "ok"}
