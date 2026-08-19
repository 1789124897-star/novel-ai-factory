"""视频制作 schemas"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class VideoForm(BaseModel):
    """视频制作表单"""

    # ── 背景视频 / BGM ──
    video_source: Literal["default", "upload"] = "default"
    bgm_source: Literal["default", "upload", "none"] = "default"

    # ── 音频 ──
    audio_source: Literal["tts", "upload"] = "tts"
    audio_tts_task_id: str = Field(default="", max_length=64)

    # ── 字幕 ──
    srt_source: Literal["tts", "upload", "none"] = "tts"
    srt_tts_task_id: str = Field(default="", max_length=64)

    # ── 上传文件名（先经 /api/upload 上传到暂存区，这里只传落盘名）──
    audio_filename: str = Field(default="", max_length=200)
    srt_filename: str = Field(default="", max_length=200)
    video_filenames: list[str] = Field(default_factory=list, max_length=30)
    bgm_filename: str = Field(default="", max_length=200)

    # ── 其他 ──
    theme: str = Field(default="", max_length=200)
    watermark_text: str = Field(default="", max_length=100)

    @model_validator(mode="after")
    def check_sources(self) -> VideoForm:
        """source 为 tts/upload 时，必须给出对应任务 id 或文件名。"""
        if self.audio_source == "tts" and not self.audio_tts_task_id:
            raise ValueError("audio_source=tts 时必须提供 audio_tts_task_id")
        if self.audio_source == "upload" and not self.audio_filename:
            raise ValueError("audio_source=upload 时必须先上传音频文件")
        if self.srt_source == "tts" and not self.srt_tts_task_id:
            raise ValueError("srt_source=tts 时必须提供 srt_tts_task_id")
        if self.srt_source == "upload" and not self.srt_filename:
            raise ValueError("srt_source=upload 时必须先上传字幕文件")
        if self.video_source == "upload" and not self.video_filenames:
            raise ValueError("video_source=upload 时必须先上传背景视频")
        if self.bgm_source == "upload" and not self.bgm_filename:
            raise ValueError("bgm_source=upload 时必须先上传 BGM 文件")
        return self

