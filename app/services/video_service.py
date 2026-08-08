"""视频制作服务 — BGM 混音 + 片段拼接 + 字幕烧录 + 水印叠加"""

import logging
import math
import shutil
import threading
import uuid
from pathlib import Path
from typing import Any, Optional

import moviepy.config as mpcfg
from pydub import AudioSegment

from app.core.config import settings, Settings
from app.video.pipeline import VideoPipeline
from app.video.subtitle_renderer import SubtitleRenderer
from app.video.watermark import Watermark

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
        p = TTS_DIR / tts_task_id / "voice.mp3"
        if p.exists():
            return p
    if source == "upload":
        candidates = sorted(upload_dir.glob("audio_*"))
        if candidates:
            return candidates[0]
    return None


def _resolve_srt_path(source: str, tts_task_id: str, upload_dir: Path) -> Optional[Path]:
    if source == "tts" and tts_task_id:
        p = TTS_DIR / tts_task_id / "subtitle.srt"
        if p.exists():
            return p
    if source == "upload":
        candidates = sorted(upload_dir.glob("srt_*"))
        if candidates:
            return candidates[0]
    return None


# ── 异步任务管理 ─────────────────────────────────────────────

_tasks: dict[str, dict] = {}
_lock = threading.Lock()


def start_task(
    *,
    theme: str = "",
    audio_source: str = "tts",
    audio_tts_task_id: str = "",
    srt_source: str = "tts",
    srt_tts_task_id: str = "",
    bgm_path: str = "",
    watermark_text: str = "",
) -> str:
    """启动后台视频制作任务，返回 task_id。"""
    task_id = str(uuid.uuid4())[:8]
    _tasks[task_id] = {"status": "running", "step": "初始化", "error": None}

    thread = threading.Thread(
        target=_run_task,
        args=(task_id, theme, audio_source, audio_tts_task_id,
              srt_source, srt_tts_task_id, bgm_path, watermark_text),
        daemon=True,
    )
    thread.start()
    logger.info("视频任务已启动 task_id=%s theme=%s", task_id, theme)
    return task_id


def get_task_status(task_id: str) -> Optional[dict]:
    return _tasks.get(task_id)


def _update(task_id: str, **kwargs: Any) -> None:
    with _lock:
        if task_id in _tasks:
            _tasks[task_id].update(kwargs)


def _run_task(
    task_id: str,
    theme: str,
    audio_source: str,
    audio_tts_task_id: str,
    srt_source: str,
    srt_tts_task_id: str,
    bgm_path: str,
    watermark_text: str,
) -> None:
    try:
        task_dir = OUTPUT_DIR / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        upload_dir = task_dir / "_uploads"
        upload_dir.mkdir(exist_ok=True)

        # ── 1. 解析音频 ─────────────────────────────────
        _update(task_id, step="解析音频源")
        audio_path = _resolve_audio_path(audio_source, audio_tts_task_id, upload_dir)
        if not audio_path:
            raise FileNotFoundError("音频源不可用，请先生成 TTS 配音或上传 MP3")

        # ── 2. BGM 混音（可选）───────────────────────────
        if bgm_path:
            _update(task_id, step="BGM 混音")
            bgm_file = Path(bgm_path)
            if bgm_file.exists():
                mixed_path = task_dir / "mixed.mp3"
                _mix_bgm(audio_path, bgm_file, mixed_path)
                audio_path = mixed_path

        # ── 3. 视频拼接 ─────────────────────────────────
        _update(task_id, step="拼接背景视频")
        raw_path = task_dir / "raw.mp4"
        paths_config = __import__("app.core.paths", fromlist=["PathConfig"]).PathConfig
        vp = VideoPipeline(settings, paths_config.from_settings(settings, theme=theme))
        vp.assemble(audio_path=audio_path, output_path=raw_path)

        # ── 4. 字幕渲染（可选）───────────────────────────
        srt_path = _resolve_srt_path(srt_source, srt_tts_task_id, upload_dir) if srt_source != "none" else None
        current_video = raw_path

        if srt_path:
            _update(task_id, step="烧录字幕")
            with_sub_path = task_dir / "with_sub.mp4"
            font = ASSETS_DIR / "fonts" / "Z-SIMHEI.TTF"
            if not font.exists():
                font = settings.WATERMARK_FONT
            sr = SubtitleRenderer(font_path=font)
            sr.render(video_path=current_video, srt_path=srt_path, output_path=with_sub_path)
            current_video = with_sub_path

        # ── 5. 水印叠加（可选）───────────────────────────
        if watermark_text:
            _update(task_id, step="添加水印")
            final_path = task_dir / "final.mp4"
            wm = Watermark(settings, paths_config.from_settings(settings, theme=theme))
            wm.apply(
                input_path=current_video,
                output_path=final_path,
                author=watermark_text,
                theme=theme,
                audio_path=audio_path,
            )
            current_video = final_path

        _update(task_id, status="done", step="完成",
                video_url=output_url(f"{task_id}/{current_video.name}"))
        logger.info("视频任务完成 task_id=%s output=%s", task_id, current_video)

    except Exception as e:
        logger.exception("视频制作失败 task_id=%s", task_id)
        _update(task_id, status="error", error=str(e))
    finally:
        # 清理上传目录
        if upload_dir.exists():
            shutil.rmtree(upload_dir, ignore_errors=True)
