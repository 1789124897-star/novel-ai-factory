"""视频制作服务 — BGM 混音 + 片段拼接 + 字幕烧录 + 水印叠加"""

import logging
import math
from pathlib import Path
from typing import Optional

import moviepy.config as mpcfg
from pydub import AudioSegment

from app.core.config import settings

logger = logging.getLogger(__name__)

mpcfg.FFMPEG_BINARY = "ffmpeg"

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "output" / "video"
UPLOAD_DIR = OUTPUT_DIR / "_uploads"
TTS_DIR = Path(__file__).resolve().parent.parent.parent / "output" / "tts"
ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "assets"


def output_url(rel_path: str) -> str:
    return f"/output/video/{rel_path}"


# ── BGM 混音 ─────────────────────────────────────────────────

def _mix_bgm(voice_path: Path, bgm_path: Path, output_path: Path) -> Path:
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


# ── 路径解析 ─────────────────────────────────────────────────

def _resolve_audio_path(source: str, tts_task_id: str, upload_dir: Path) -> Optional[Path]:
    """解析音频路径。source='tts' 从 TTS 产物取，source='upload' 从上传目录取。"""
    if source == "tts" and tts_task_id:
        path = TTS_DIR / tts_task_id / "voice.mp3"
        if path.exists():
            return path
    if source == "upload":
        candidates = sorted(upload_dir.glob("audio_*"))
        if candidates:
            return candidates[0]
    return None


def _resolve_srt_path(source: str, tts_task_id: str, upload_dir: Path) -> Optional[Path]:
    if source == "tts" and tts_task_id:
        path = TTS_DIR / tts_task_id / "subtitle.srt"
        if path.exists():
            return path
    if source == "upload":
        candidates = sorted(upload_dir.glob("srt_*"))
        if candidates:
            return candidates[0]
    return None