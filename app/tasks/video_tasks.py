"""视频制作 — 异步任务调度"""

from __future__ import annotations

import logging
import multiprocessing
import shutil
import threading
from pathlib import Path
from typing import Optional

from moviepy import CompositeVideoClip, ImageClip

from app.core.config import settings
from app.core.paths import PathConfig
from app.services.task_manager import TaskManager
from app.services.video_service import VideoService
from app.video import SubtitleRenderer, VideoPipeline, Watermark

logger = logging.getLogger(__name__)

_task_manager = TaskManager()

# moviepy 渲染时会在系统临时目录写固定名字的中间文件（finalTEMP_MPY_wvf_snd.mp4），
# 并发渲染会互抢导致 WinError 32，且 ffmpeg 子进程异常时可能残留占用，故串行化渲染。
_VIDEO_RENDER_LOCK = threading.Lock()


def new_task_id() -> str:
    """向任务管理器要一个新任务号（上传文件落位需提前取号）。"""
    return _task_manager.next_id()


def start_task(
    *,
    task_id: Optional[str] = None,
    theme: str = "",
    audio_source: str = "tts",
    audio_tts_task_id: str = "",
    srt_source: str = "tts",
    srt_tts_task_id: str = "",
    video_source: str = "default",
    bg_video_paths: Optional[list[str]] = None,
    bgm_source: str = "default",
    bgm_path: str = "",
    watermark_text: str = "",
) -> str:
    """启动后台视频制作任务，返回 task_id。"""
    task_id = _task_manager.start(
        _do_video,
        theme,
        audio_source,
        audio_tts_task_id,
        srt_source,
        srt_tts_task_id,
        video_source,
        bg_video_paths or [],
        bgm_source,
        bgm_path,
        watermark_text,
        task_id=task_id,
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
    video_source: str,
    bg_video_paths: list[str],
    bgm_source: str,
    bgm_path: str,
    watermark_text: str,
) -> None:
    """后台执行视频制作管线。"""
    upload_dir = None
    try:
        paths = PathConfig.from_settings(settings, theme=theme)
        upload_dir = paths.video_task_upload_dir(task_id)

        # 1. 解析音频
        _task_manager.update(task_id, step="解析音频源")
        audio_path = VideoService.resolve_audio_path(audio_source, audio_tts_task_id, upload_dir)
        if not audio_path:
            raise FileNotFoundError("音频源不可用")

        # 2. BGM 混音
        resolved_bgm: Optional[Path] = None
        if bgm_source == "default":
            default_bgm = paths.default_bgm_path
            if default_bgm.exists():
                resolved_bgm = default_bgm
        elif bgm_source == "upload" and bgm_path:
            p = Path(bgm_path)
            if p.exists():
                resolved_bgm = p

        if resolved_bgm:
            _task_manager.update(task_id, step="BGM 混音")
            mixed_path = paths.video_task_mixed_audio_file(task_id)
            VideoService.mix_bgm(audio_path, resolved_bgm, mixed_path)
            audio_path = mixed_path

        # 3. 视频拼接（内存）
        _task_manager.update(task_id, step="拼接背景视频")
        video_pipeline = VideoPipeline(settings, paths)
        video_clip = video_pipeline.assemble(
            audio_path=audio_path,
            video_paths=[Path(p) for p in bg_video_paths] if video_source == "upload" and bg_video_paths else None,
        )

        # 4. 收集字幕 + 水印叠加层（内存）
        overlay_clips: list[ImageClip] = []

        srt_path = VideoService.resolve_srt_path(srt_source, srt_tts_task_id, upload_dir) if srt_source != "none" else None
        if srt_path:
            _task_manager.update(task_id, step="烧录字幕")
            subtitle_renderer = SubtitleRenderer(settings, paths)
            overlay_clips.extend(subtitle_renderer.build_sub_clips(srt_path, video_clip.size))

        if theme or watermark_text:
            _task_manager.update(task_id, step="添加水印")
            watermark = Watermark(settings, paths)
            overlay_clips.extend(watermark.build_overlay_clips(
                video_clip.size,
                video_clip.duration,
                author=watermark_text,
                theme=theme,
                audio_path=audio_path,
            ))

        # 5. 统一编码
        _task_manager.update(task_id, step="编码输出")
        output_path = paths.video_task_final_video_file(task_id)
        final = CompositeVideoClip([video_clip, *overlay_clips], size=video_clip.size)

        threads = max(1, multiprocessing.cpu_count() // 2)
        logger.info("正在导出视频 (%d 线程) …", threads)
        try:
            with _VIDEO_RENDER_LOCK:
                final.write_videofile(
                    str(output_path),
                    codec="libx264",
                    audio_codec="aac",
                    fps=24,
                    preset="ultrafast",
                    threads=threads,
                )
        finally:
            # 异常时确保释放 ffmpeg 子进程与临时文件句柄，防止僵尸进程占用
            final.close()
        logger.info("视频已保存 → %s", output_path)

        _task_manager.update(task_id, step="完成", video_url=VideoService.output_url(f"{task_id}/{output_path.name}"))
        logger.info("视频任务完成 task_id=%s", task_id)

    finally:
        if upload_dir and upload_dir.exists():
            shutil.rmtree(upload_dir, ignore_errors=True)
