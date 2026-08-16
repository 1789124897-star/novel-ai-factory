"""一键生成 — 全链路编排路由"""

from typing import Optional

from fastapi import APIRouter, Form, HTTPException, UploadFile

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
    video_files: list[UploadFile] = [],
    bgm_file: Optional[UploadFile] = None,
) -> dict:
    """启动全链路编排任务。

    上传文件在请求阶段读入内存（背景视频/BGM 需等到最后的视频步骤才使用，
    此时 UploadFile 句柄已随请求结束而关闭），后台任务后续从内存解析。
    """
    try:
        video_files_data = (
            [(f.filename, await f.read()) for f in video_files if f.filename] or None
        )
        bgm_file_data = (
            (bgm_file.filename, await bgm_file.read())
            if bgm_file and bgm_file.filename
            else None
        )
    except Exception as e:
        raise HTTPException(500, f"读取上传文件失败: {e}")

    task_id = pipeline_tasks.start_pipeline(
        theme=theme.strip(),
        target_words=target_words,
        voice=voice,
        rate=rate,
        video_source=video_source,
        bgm_source=bgm_source,
        watermark_theme=watermark_theme.strip(),
        watermark_author=watermark_author.strip(),
        video_files_data=video_files_data,
        bgm_file_data=bgm_file_data,
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
    # 上传文件 bytes 仅内存暂存供续跑使用，不参与轮询响应，避免大体积序列化
    state = {k: v for k, v in state.items() if k not in ("video_files_data", "bgm_file_data")}
    return {"data": {"task_id": task_id, **state}, "message": "ok"}
