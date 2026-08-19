"""一键生成管线 schemas"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class PipelineForm(BaseModel):
    """一键生成表单"""

    # ── 故事输入 ──
    theme: str = Field(min_length=1, max_length=200, description="故事主题")
    target_words: int = Field(default=8000, ge=100, le=50000, description="目标字数")

    # ── TTS 配音 ──
    voice: str = Field(min_length=1, description="edge-tts 音色")
    rate: str = Field(pattern=r"^[+-]\d+%$", description="语速")

    # ── 背景视频 / BGM ──
    video_source: Literal["default", "upload"] = "default"
    bgm_source: Literal["default", "upload", "none"] = "default"

    # 上传文件名
    video_filenames: list[str] = Field(default_factory=list, max_length=30)
    bgm_filename: str = Field(default="", max_length=200)

    # ── 水印 ──
    watermark_theme: str = Field(default="", max_length=100)
    watermark_author: str = Field(default="", max_length=50)

    @model_validator(mode="after")
    def check_upload_files(self) -> PipelineForm:
        if self.video_source == "upload" and not self.video_filenames:
            raise ValueError("video_source=upload 时必须先上传背景视频")
        if self.bgm_source == "upload" and not self.bgm_filename:
            raise ValueError("bgm_source=upload 时必须先上传 BGM 文件")
        return self


class ResumeRequest(BaseModel):
    """续跑请求"""

    old_task_id: str = Field(min_length=1, max_length=64, description="原任务 id")
