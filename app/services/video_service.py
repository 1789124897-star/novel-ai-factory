"""视频制作服务 — 上传处理 + BGM 混音 + 路径解析。"""

import logging
import math
import shutil
from pathlib import Path
from typing import Optional

import moviepy.config as mpcfg
from fastapi import UploadFile
from pydub import AudioSegment

from app.core.config import settings
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
        audio_file: Optional[UploadFile] = None,
        srt_file: Optional[UploadFile] = None,
        video_files: Optional[list[UploadFile]] = None,
        bgm_file: Optional[UploadFile] = None,
    ) -> str:
        """保存上传文件并提交视频制作任务，返回 task_id。"""
        from app.tasks import video_tasks  # 延迟导入避免循环依赖

        # 提前取号：上传文件需落到该任务的专属目录，任务执行时从同目录解析
        task_id = video_tasks.new_task_id()
        upload_dir = PathConfig.from_settings(settings, theme="").video_output / task_id / "_uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)

        bg_video_paths, bgm_path = save_uploads(
            upload_dir=upload_dir,
            audio_source=audio_source,
            srt_source=srt_source,
            video_source=video_source,
            bgm_source=bgm_source,
            audio_file=audio_file,
            srt_file=srt_file,
            video_files=video_files,
            bgm_file=bgm_file,
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
    def output_url(rel_path: str) -> str:
        return f"/output/video/{rel_path}"

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
    def resolve_audio_path(source: str, tts_task_id: str, upload_dir: Path, tts_dir: Path) -> Optional[Path]:
        """解析音频路径。source='tts' 从 TTS 产物取，source='upload' 从上传目录取。"""
        if source == "tts" and tts_task_id:
            path = tts_dir / tts_task_id / "voice.mp3"
            if path.exists():
                return path
        if source == "upload":
            candidates = sorted(upload_dir.glob("audio_*"))
            if candidates:
                return candidates[0]
        return None

    @staticmethod
    def resolve_srt_path(source: str, tts_task_id: str, upload_dir: Path, tts_dir: Path) -> Optional[Path]:
        """解析字幕路径。source='tts' 从 TTS 产物取，source='upload' 从上传目录取。"""
        if source == "tts" and tts_task_id:
            path = tts_dir / tts_task_id / "subtitle.srt"
            if path.exists():
                return path
        if source == "upload":
            candidates = sorted(upload_dir.glob("srt_*"))
            if candidates:
                return candidates[0]
        return None


# ── 上传文件保存 ──────────────────────────────────────

def save_uploads(
    *,
    upload_dir: Path,
    audio_source: str,
    audio_file: Optional[UploadFile] = None,

    srt_source: str,
    srt_file: Optional[UploadFile] = None,

    video_source: str,
    video_files: Optional[list[UploadFile]] = None,

    bgm_source: str,
    bgm_file: Optional[UploadFile] = None,

) -> tuple[list[str], str]:
    """保存上传文件到任务专属上传目录。"""
    bg_video_paths: list[str] = []
    bgm_path = ""

    if audio_source == "upload" and audio_file and audio_file.filename:
        _save_upload_file(upload_dir, "audio_", audio_file)
    if srt_source == "upload" and srt_file and srt_file.filename:
        _save_upload_file(upload_dir, "srt_", srt_file)
    if video_source == "upload" and video_files:
        for vf in video_files:
            if vf.filename:
                dest = _save_upload_file(upload_dir, "bg_", vf)
                bg_video_paths.append(str(dest))
    if bgm_source == "upload" and bgm_file and bgm_file.filename:
        dest = _save_upload_file(upload_dir, "bgm_", bgm_file)
        bgm_path = str(dest)

    return bg_video_paths, bgm_path


def _save_upload_file(upload_dir: Path, prefix: str, file: UploadFile) -> Path:
    dest = upload_dir / f"{prefix}{file.filename}"
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return dest

