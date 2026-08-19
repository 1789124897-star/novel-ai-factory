"""视频制作服务 — 文件暂存/搬运 + BGM 混音 + 路径解析。"""

from __future__ import annotations

import logging
import math
import shutil
from pathlib import Path
from typing import Optional
from uuid import uuid4

import moviepy.config as mpcfg
from fastapi import HTTPException, UploadFile
from pydub import AudioSegment

from app.core.config import settings
from app.core.constants import MAX_UPLOAD_MB, OUTPUT_URL_PREFIX
from app.core.paths import PathConfig

logger = logging.getLogger(__name__)

# ── 常量 ──────────────────────────────────────────────

mpcfg.FFMPEG_BINARY = "ffmpeg"


# ── 公开 API ──────────────────────────────────────────

class VideoService:
    """视频制作服务 — 任务提交入口。"""

    @staticmethod
    def start_video_task(
        *,
        audio_source: str,
        audio_tts_task_id: str,
        srt_source: str,
        srt_tts_task_id: str,
        video_source: str,
        bgm_source: str,
        theme: str = "",
        watermark_text: str = "",
        audio_filename: str = "",
        srt_filename: str = "",
        video_filenames: Optional[list[str]] = None,
        bgm_filename: str = "",
    ) -> str:
        """提交视频制作任务，返回 task_id。

        文件已先经 /api/upload 落到暂存区，这里把暂存文件搬入任务专属目录。
        """
        from app.tasks import video_tasks  # 延迟导入避免循环依赖

        # 提前取号：上传文件需落到该任务的专属目录，任务执行时从同目录解析
        task_id = video_tasks.new_task_id()
        upload_dir = PathConfig.from_settings(settings, theme="").video_task_upload_dir(task_id)

        bg_video_paths, bgm_path = stage_files_to_uploads(
            upload_dir=upload_dir,
            audio_source=audio_source,
            audio_filename=audio_filename,
            srt_source=srt_source,
            srt_filename=srt_filename,
            video_source=video_source,
            video_filenames=video_filenames,
            bgm_source=bgm_source,
            bgm_filename=bgm_filename,
        )
        return video_tasks.start_task(
            task_id=task_id,
            audio_source=audio_source,
            audio_tts_task_id=audio_tts_task_id,
            srt_source=srt_source,
            srt_tts_task_id=srt_tts_task_id,
            video_source=video_source,
            bg_video_paths=bg_video_paths,
            bgm_source=bgm_source,
            bgm_path=bgm_path,
            theme=theme,
            watermark_text=watermark_text,
        )

    @staticmethod
    def start_pipeline_task(
        *,
        theme: str,
        target_words: int,
        voice: str,
        rate: str,
        video_source: str,
        bgm_source: str,
        watermark_theme: str = "",
        watermark_author: str = "",
        video_filenames: Optional[list[str]] = None,
        bgm_filename: str = "",
    ) -> str:
        """提交一键生成任务，返回 task_id。"""
        from app.tasks import pipeline_tasks  # 延迟导入避免循环依赖

        # 提前取id，落盘上传的文件
        task_id = pipeline_tasks.new_task_id()
        upload_dir = PathConfig.from_settings(settings, theme="").video_task_upload_dir(task_id)

        video_paths, bgm_path = stage_files_to_uploads(
            upload_dir=upload_dir,
            audio_source="tts",
            audio_filename="",
            srt_source="tts",
            srt_filename="",
            video_source=video_source,
            video_filenames=video_filenames,
            bgm_source=bgm_source,
            bgm_filename=bgm_filename,
        )
        return pipeline_tasks.start_pipeline(
            theme=theme,
            target_words=target_words,
            voice=voice,
            rate=rate,
            video_source=video_source,
            bgm_source=bgm_source,
            watermark_theme=watermark_theme,
            watermark_author=watermark_author,
            video_paths=video_paths,
            bgm_path=bgm_path,
            task_id=task_id,
        )

    @staticmethod
    def output_url(rel_path: str) -> str:
        return f"{OUTPUT_URL_PREFIX}/video/{rel_path}"

    # ── BGM 混音 ───────────────────────────────────

    @staticmethod
    def mix_bgm(voice_path: Path, bgm_path: Path, output_path: Path) -> Path:
        """将 BGM 混入语音，音量比从配置读取。"""
        voice = AudioSegment.from_file(voice_path)
        bgm = AudioSegment.from_file(bgm_path)

        db_change = 20 * math.log10(settings.BGM_VOLUME_RATIO)
        bgm = bgm + db_change

        if len(bgm) < len(voice):
            loops = math.ceil(len(voice) / len(bgm))
            bgm = (bgm * loops)[:len(voice)]
        else:
            bgm = bgm[:len(voice)]

        mixed = voice.overlay(bgm)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        mixed.export(output_path, format="mp3", bitrate="320k")
        logger.info("BGM 混音完成 → %s", output_path)
        return output_path

    # ── 路径解析 ───────────────────────────────────

    @staticmethod
    def resolve_audio_path(source: str, tts_task_id: str, upload_dir: Path) -> Optional[Path]:
        """解析音频路径。source='tts' 从 TTS 产物取，source='upload' 从上传目录取。"""
        if source == "tts" and tts_task_id:
            voice_path = PathConfig.from_settings(settings, theme="").tts_voice_file(tts_task_id)
            if voice_path.exists():
                return voice_path
        if source == "upload":
            candidates = sorted(upload_dir.glob("audio_*"))
            if candidates:
                return candidates[0]
        return None

    @staticmethod
    def resolve_srt_path(source: str, tts_task_id: str, upload_dir: Path) -> Optional[Path]:
        """解析字幕路径。source='tts' 从 TTS 产物取，source='upload' 从上传目录取。"""
        if source == "tts" and tts_task_id:
            subtitle_path = PathConfig.from_settings(settings, theme="").tts_subtitle_file(tts_task_id)
            if subtitle_path.exists():
                return subtitle_path
        if source == "upload":
            candidates = sorted(upload_dir.glob("srt_*"))
            if candidates:
                return candidates[0]
        return None


# ── 上传文件暂存与搬运 ──────────────────────────────────

def save_staging_file(file: UploadFile, allowed_extensions: set[str]) -> str:
    """校验并保存上传文件到暂存区，返回落盘文件名"""

    filename = Path(file.filename or "").name
    if not filename:
        raise HTTPException(422, "上传文件名为空")

    suffix = Path(filename).suffix.lower()
    if suffix not in allowed_extensions:
        raise HTTPException(422, f"不支持的文件类型 {suffix}，允许：{', '.join(sorted(allowed_extensions))}")

    staging_dir = PathConfig.from_settings(settings, theme="").staging_dir
    staging_name = f"{uuid4().hex[:8]}_{filename}"
    dest = staging_dir / staging_name

    size = 0
    try:
        with dest.open("wb") as f:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_MB * 1024 * 1024:
                    raise HTTPException(422, f"文件超过大小上限 {MAX_UPLOAD_MB}MB")
                f.write(chunk)
    except HTTPException:
        dest.unlink(missing_ok=True)
        raise
    return staging_name


def move_staging_files(staging_names: list[str], upload_dir: Path, prefix: str) -> list[str]:
    """把暂存文件搬入任务专属目录"""
    staging_dir = PathConfig.from_settings(settings, theme="").staging_dir
    upload_dir.mkdir(parents=True, exist_ok=True)
    moved_paths: list[str] = []
    for staging_name in staging_names:
        safe_name = Path(staging_name).name
        staging_path = staging_dir / safe_name
        if not staging_path.exists():
            raise HTTPException(422, f"上传文件不存在或已失效：{staging_name}")
        original_name = staging_name.split("_", 1)[-1]
        task_path = upload_dir / f"{prefix}{original_name}"
        shutil.move(str(staging_path), str(task_path))
        moved_paths.append(str(task_path))
    return moved_paths


def stage_files_to_uploads(
    *,
    upload_dir: Path,
    audio_source: str,
    audio_filename: str,
    srt_source: str,
    srt_filename: str,
    video_source: str,
    video_filenames: Optional[list[str]] = None,
    bgm_source: str,
    bgm_filename: str,
) -> tuple[list[str], str]:
    """把暂存文件搬入任务专属上传目录，返回背景视频路径列表和 BGM 路径。"""
    bg_video_paths: list[str] = []
    bgm_path = ""

    if audio_source == "upload" and audio_filename:
        move_staging_files([audio_filename], upload_dir, "audio_")
    if srt_source == "upload" and srt_filename:
        move_staging_files([srt_filename], upload_dir, "srt_")
    if video_source == "upload" and video_filenames:
        bg_video_paths = move_staging_files(video_filenames, upload_dir, "bg_")
    if bgm_source == "upload" and bgm_filename:
        bgm_path = move_staging_files([bgm_filename], upload_dir, "bgm_")[0]

    return bg_video_paths, bgm_path

