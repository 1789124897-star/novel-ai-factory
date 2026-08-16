"""视频路由"""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Form, HTTPException, UploadFile

from app.services.video_service import VideoService
from app.tasks import video_tasks

router = APIRouter(prefix="/api/video", tags=["Video"])

VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov"}
VIDEO_DIR = Path(__file__).resolve().parent.parent.parent.parent / "assets" / "videos"


@router.get("/clips")
async def list_clips() -> dict:
    """查询可用背景视频片段数量"""
    count = 0
    if VIDEO_DIR.exists():
        count = sum(1 for p in VIDEO_DIR.iterdir() if p.suffix.lower() in VIDEO_EXTENSIONS)
    return {"data": {"count": count}, "message": "ok"}


@router.post("")
async def start_video(
    # ── 音频 ──
    audio_source: str = Form("tts"),
    audio_tts_task_id: str = Form(""),
    audio_file: Optional[UploadFile] = None,

    # ── 字幕 ──
    srt_source: str = Form("tts"),
    srt_tts_task_id: str = Form(""),
    srt_file: Optional[UploadFile] = None,

    # ── 背景视频 ──
    video_source: str = Form("default"),
    video_files: Optional[list[UploadFile]] = None,

    # ── BGM ──
    bgm_source: str = Form("default"),
    bgm_file: Optional[UploadFile] = None,

    # ── 其他 ──
    theme: str = Form(""),
    watermark_text: str = Form(""),
) -> dict:
    """启动视频制作任务。"""
    task_id = VideoService.start_video_task(

        audio_source=audio_source,
        audio_tts_task_id=audio_tts_task_id,
        audio_file=audio_file,

        srt_source=srt_source,
        srt_tts_task_id=srt_tts_task_id,
        srt_file=srt_file,

        video_source=video_source,
        video_files=video_files,

        bgm_source=bgm_source,
        bgm_file=bgm_file,

        theme=theme.strip(),
        watermark_text=watermark_text.strip(),
    )
    return {"data": {"task_id": task_id}, "message": "ok"}


@router.get("/{task_id}")
async def get_video_status(task_id: str) -> dict:
    """轮询视频任务状态"""
    state = video_tasks.get_task_status(task_id)
    if not state:
        raise HTTPException(404, "任务不存在")
    return {"data": {"task_id": task_id, **state}, "message": "ok"}
