"""一键生成 — 全链路编排路由"""

from typing import Optional

from fastapi import APIRouter, Form, HTTPException, UploadFile

from app.core.config import settings
from app.core.paths import PathConfig
from app.services.video_service import save_uploads
from app.tasks import pipeline_tasks

router = APIRouter(prefix="/api/pipeline", tags=["Pipeline"])


@router.post("")
async def start_pipeline(
    theme: str = Form(...),
    target_words: int = Form(8000),
    voice: str = Form("zh-CN-XiaoxiaoNeural"),
    rate: str = Form("+0%"),
    video_source: str = Form("default"),
    bgm_source: str = Form("default"),
    watermark_theme: str = Form(""),
    watermark_author: str = Form(""),
    video_files: Optional[list[UploadFile]] = None,
    bgm_file: Optional[UploadFile] = None,
) -> dict:
    """启动全链路编排任务。

    上传文件在请求阶段落盘到任务专属目录（背景视频/BGM 需等到最后的
    视频步骤才使用，此时 UploadFile 句柄已随请求结束而关闭），
    后台任务从磁盘路径解析，续跑时直接复用路径。
    """
    # 提前取号：上传文件需落到该任务的专属目录，任务执行时从同目录解析
    task_id = pipeline_tasks.new_task_id()
    upload_dir = PathConfig.from_settings(settings, theme="").video_output / task_id / "_uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    try:
        video_paths, bgm_path = save_uploads(
            upload_dir=upload_dir,
            audio_source="tts",
            srt_source="tts",
            video_source=video_source,
            bgm_source=bgm_source,
            video_files=video_files,
            bgm_file=bgm_file,
        )
    except Exception as e:
        raise HTTPException(500, f"保存上传文件失败: {e}") from e

    task_id = pipeline_tasks.start_pipeline(
        theme=theme.strip(),
        target_words=target_words,
        voice=voice,
        rate=rate,
        video_source=video_source,
        bgm_source=bgm_source,
        watermark_theme=watermark_theme.strip(),
        watermark_author=watermark_author.strip(),
        video_paths=video_paths,
        bgm_path=bgm_path,
        task_id=task_id,
    )
    return {"data": {"task_id": task_id}, "message": "ok"}


@router.post("/resume")
async def resume_pipeline(old_task_id: str = Form(...)) -> dict:
    """从上次失败的阶段续跑，复用已完成步骤的产物。"""
    if not pipeline_tasks.get_pipeline_status(old_task_id):
        raise HTTPException(404, "原任务不存在")
    task_id = pipeline_tasks.resume_pipeline(old_task_id)
    return {"data": {"task_id": task_id}, "message": "ok"}


@router.get("/{task_id}")
async def get_pipeline_status(task_id: str) -> dict:
    """查询编排任务状态（轮询进度用）。"""
    state = pipeline_tasks.get_pipeline_status(task_id)
    if not state:
        raise HTTPException(404, "任务不存在")
    return {"data": {"task_id": task_id, **state}, "message": "ok"}
