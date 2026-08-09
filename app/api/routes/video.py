"""视频路由"""

import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Form, HTTPException, UploadFile

from app.services import video_service
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
    audio_source: str = Form("tts"),
    audio_tts_task_id: str = Form(""),
    audio_file: Optional[UploadFile] = None,
    srt_source: str = Form("tts"),
    srt_tts_task_id: str = Form(""),
    srt_file: Optional[UploadFile] = None,
    bgm_file: Optional[UploadFile] = None,
    watermark_text: str = Form(""),
) -> dict:
    """启动视频制作任务"""
    upload_dir = video_service.UPLOAD_DIR
    upload_dir.mkdir(parents=True, exist_ok=True)
    bgm_path = ""

    # 保存上传文件到 upload_dir
    if audio_source == "upload" and audio_file:
        dest = upload_dir / f"audio_{audio_file.filename}"
        with dest.open("wb") as f:
            shutil.copyfileobj(audio_file.file, f)
    if srt_source == "upload" and srt_file:
        dest = upload_dir / f"srt_{srt_file.filename}"
        with dest.open("wb") as f:
            shutil.copyfileobj(srt_file.file, f)
    if bgm_file:
        dest = upload_dir / f"bgm_{bgm_file.filename}"
        with dest.open("wb") as f:
            shutil.copyfileobj(bgm_file.file, f)
        bgm_path = str(dest)

    try:
        task_id = video_tasks.start_task(
            audio_source=audio_source,
            audio_tts_task_id=audio_tts_task_id,
            srt_source=srt_source,
            srt_tts_task_id=srt_tts_task_id,
            bgm_path=bgm_path,
            watermark_text=watermark_text.strip(),
        )
        return {"data": {"task_id": task_id}, "message": "ok"}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/{task_id}")
async def get_video_status(task_id: str) -> dict:
    """轮询视频任务状态"""
    state = video_tasks.get_task_status(task_id)
    if not state:
        raise HTTPException(404, "任务不存在")
    return {"data": {"task_id": task_id, **state}, "message": "ok"}
