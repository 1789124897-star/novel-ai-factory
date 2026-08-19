"""一键生成 — 全链路编排路由"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.pipeline import PipelineForm, ResumeRequest
from app.services.video_service import VideoService
from app.tasks import pipeline_tasks

router = APIRouter(prefix="/api/pipeline", tags=["Pipeline"])


@router.post("")
async def start_pipeline(form: PipelineForm) -> dict:
    """启动全链路编排任务"""
    task_id = VideoService.start_pipeline_task(
        theme=form.theme.strip(),
        target_words=form.target_words,
        voice=form.voice,
        rate=form.rate,
        video_source=form.video_source,
        video_filenames=form.video_filenames,
        bgm_source=form.bgm_source,
        bgm_filename=form.bgm_filename,
        watermark_theme=form.watermark_theme.strip(),
        watermark_author=form.watermark_author.strip(),
    )
    return {"data": {"task_id": task_id}, "message": "ok"}


@router.post("/resume")
async def resume_pipeline(body: ResumeRequest) -> dict:
    """从上次失败的阶段续跑，复用已完成步骤的产物。"""
    if not pipeline_tasks.get_pipeline_status(body.old_task_id):
        raise HTTPException(404, "原任务不存在")
    task_id = pipeline_tasks.resume_pipeline(body.old_task_id)
    return {"data": {"task_id": task_id}, "message": "ok"}


@router.get("/{task_id}")
async def get_pipeline_status(task_id: str) -> dict:
    """查询编排任务状态（轮询进度用）。"""
    state = pipeline_tasks.get_pipeline_status(task_id)
    if not state:
        raise HTTPException(404, "任务不存在")
    return {"data": {"task_id": task_id, **state}, "message": "ok"}
