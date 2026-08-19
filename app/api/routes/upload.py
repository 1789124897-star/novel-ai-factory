"""文件上传路由 — 上传到暂存区，业务接口 JSON 里引用文件名。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.constants import (
    AUDIO_ALLOWED_EXTENSIONS,
    SRT_ALLOWED_EXTENSIONS,
    VIDEO_ALLOWED_EXTENSIONS,
)
from app.services.video_service import save_staging_file

router = APIRouter(prefix="/api/upload", tags=["Upload"])

ROLE_EXTENSIONS = {
    "video": VIDEO_ALLOWED_EXTENSIONS,
    "audio": AUDIO_ALLOWED_EXTENSIONS,
    "srt": SRT_ALLOWED_EXTENSIONS,
}


@router.post("")
async def upload_file(
    role: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
) -> dict:
    """上传文件到暂存区，返回落盘文件名；任务接口 JSON 里带上该名。"""
    allowed_extensions = ROLE_EXTENSIONS.get(role)
    if allowed_extensions is None:
        raise HTTPException(422, f"未知文件角色 {role}，允许：{', '.join(ROLE_EXTENSIONS)}")
    filename = save_staging_file(file, allowed_extensions)
    return {"data": {"filename": filename}, "message": "ok"}
