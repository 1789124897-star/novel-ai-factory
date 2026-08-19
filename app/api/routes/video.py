"""视频路由"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.core.constants import VIDEO_ALLOWED_EXTENSIONS
from app.core.paths import PathConfig
from app.schemas.video import VideoForm
from app.services.video_service import VideoService
from app.tasks import video_tasks

router = APIRouter(prefix="/api/video", tags=["Video"])

VIDEO_DIR = PathConfig.from_settings(settings, theme="").video_clip_dir


@router.get("/clips")
async def list_clips() -> dict:
    """查询可用背景视频片段数量"""
    count = 0
    if VIDEO_DIR.exists():
        count = sum(1 for p in VIDEO_DIR.iterdir() if p.suffix.lower() in VIDEO_ALLOWED_EXTENSIONS)
    return {"data": {"count": count}, "message": "ok"}


@router.post("")
async def start_video(form: VideoForm) -> dict:
    """启动视频制作任务"""
    task_id = VideoService.start_video_task(
        audio_source=form.audio_source,
        audio_tts_task_id=form.audio_tts_task_id,
        audio_filename=form.audio_filename,
        srt_source=form.srt_source,
        srt_tts_task_id=form.srt_tts_task_id,
        srt_filename=form.srt_filename,
        video_source=form.video_source,
        video_filenames=form.video_filenames,
        bgm_source=form.bgm_source,
        bgm_filename=form.bgm_filename,
        theme=form.theme.strip(),
        watermark_text=form.watermark_text.strip(),
    )
    return {"data": {"task_id": task_id}, "message": "ok"}


@router.get("/{task_id}")
async def get_video_status(task_id: str) -> dict:
    """轮询视频任务状态"""
    state = video_tasks.get_task_status(task_id)
    if not state:
        raise HTTPException(404, "任务不存在")
    return {"data": {"task_id": task_id, **state}, "message": "ok"}
