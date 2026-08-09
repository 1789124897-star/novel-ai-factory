"""视频制作 — 异步任务调度"""

import logging
import shutil
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.core.paths import PathConfig
from app.services.task_manager import TaskManager
from app.services.video_service import (
    OUTPUT_DIR,
    ASSETS_DIR,
    _resolve_audio_path,
    _resolve_srt_path,
    _mix_bgm,
    output_url,
)
from app.video.pipeline import VideoPipeline
from app.video.subtitle_renderer import SubtitleRenderer
from app.video.watermark import Watermark

logger = logging.getLogger(__name__)

_task_manager = TaskManager()


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
    task_id = _task_manager.start(
        _do_video,
        theme, audio_source, audio_tts_task_id,
        srt_source, srt_tts_task_id, bgm_path, watermark_text,
        step="初始化",
    )
    logger.info("视频任务已启动 task_id=%s theme=%s", task_id, theme)
    return task_id


def get_task_status(task_id: str) -> Optional[dict]:
    """查询任务状态。"""
    return _task_manager.get(task_id)


def _do_video(
    task_id: str,
    theme: str,
    audio_source: str,
    audio_tts_task_id: str,
    srt_source: str,
    srt_tts_task_id: str,
    bgm_path: str,
    watermark_text: str,
) -> None:
    """后台执行视频制作管线。异常由 TaskManager._wrap 统一捕获。"""
    upload_dir = None
    try:
        task_dir = OUTPUT_DIR / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        upload_dir = task_dir / "_uploads"
        upload_dir.mkdir(exist_ok=True)

        # 1. 解析音频
        _task_manager.update(task_id, step="解析音频源")
        audio_path = _resolve_audio_path(audio_source, audio_tts_task_id, upload_dir)
        if not audio_path:
            raise FileNotFoundError("音频源不可用，请先生成 TTS 配音或上传 MP3")

        # 2. BGM 混音（可选）
        if bgm_path:
            _task_manager.update(task_id, step="BGM 混音")
            bgm_file = Path(bgm_path)
            if bgm_file.exists():
                mixed_path = task_dir / "mixed.mp3"
                _mix_bgm(audio_path, bgm_file, mixed_path)
                audio_path = mixed_path

        # 3. 视频拼接
        _task_manager.update(task_id, step="拼接背景视频")
        raw_path = task_dir / "raw.mp4"
        video_pipeline = VideoPipeline(settings, PathConfig.from_settings(settings, theme=theme))
        video_pipeline.assemble(audio_path=audio_path, output_path=raw_path)

        # 4. 字幕渲染（可选）
        srt_path = _resolve_srt_path(srt_source, srt_tts_task_id, upload_dir) if srt_source != "none" else None
        current_video = raw_path

        if srt_path:
            _task_manager.update(task_id, step="烧录字幕")
            with_sub_path = task_dir / "with_sub.mp4"
            font = ASSETS_DIR / "fonts" / "Z-SIMHEI.TTF"
            if not font.exists():
                font = settings.WATERMARK_FONT
            subtitle_renderer = SubtitleRenderer(font_path=font)
            subtitle_renderer.render(video_path=current_video, srt_path=srt_path, output_path=with_sub_path)
            current_video = with_sub_path

        # 5. 水印叠加（可选）
        if watermark_text:
            _task_manager.update(task_id, step="添加水印")
            final_path = task_dir / "final.mp4"
            watermark = Watermark(settings, PathConfig.from_settings(settings, theme=theme))
            watermark.apply(
                input_path=current_video,
                output_path=final_path,
                author=watermark_text,
                theme=theme,
                audio_path=audio_path,
            )
            current_video = final_path

        _task_manager.update(task_id, step="完成", video_url=output_url(f"{task_id}/{current_video.name}"))
        logger.info("视频任务完成 task_id=%s output=%s", task_id, current_video)

    finally:
        if upload_dir and upload_dir.exists():
            shutil.rmtree(upload_dir, ignore_errors=True)
