"""视频拼接 — 连接背景片段并叠加混合音频。"""

import logging
import multiprocessing
from pathlib import Path
from typing import TYPE_CHECKING

from moviepy import (
    AudioFileClip,
    VideoFileClip,
    concatenate_videoclips,
)

if TYPE_CHECKING:
    from ..core.config import Settings
    from ..core.paths import PathConfig

logger = logging.getLogger(__name__)

VIDEO_EXTENSIONS = (".mp4", ".avi", ".mov")


class VideoPipeline:
    """选择背景片段，拼接并叠加音频。"""

    def __init__(self, settings: "Settings", paths: "PathConfig"):
        self._settings = settings
        self._paths = paths

    # ── 素材收集 ──────────────────────────────────────

    def _collect_clips(
        self, start_index: int, target_duration: float
    ) -> list[Path]:
        all_clips = sorted(
            clip_path
            for clip_path in self._paths.video_clip_dir.iterdir()
            if clip_path.suffix.lower() in VIDEO_EXTENSIONS
        )
        if not all_clips:
            raise FileNotFoundError(
                f"{self._paths.video_clip_dir} 中未找到视频片段"
            )

        candidates = all_clips[start_index:]
        if not candidates:
            raise ValueError(
                f"start_index={start_index} 后无可用片段 "
                f"(total: {len(all_clips)})"
            )

        selected: list[Path] = []
        accumulated = 0.0

        for i, clip_path in enumerate(candidates, 1):
            try:
                with VideoFileClip(str(clip_path)) as clip:
                    if clip.duration <= 0:
                        continue
                    selected.append(clip_path)
                    accumulated += clip.duration
                    logger.info(
                        "[%d/%d] %s  dur=%.1fs  acc=%.1fs",
                        i,
                        len(candidates),
                        clip_path.name,
                        clip.duration,
                        accumulated,
                    )
                    if accumulated >= target_duration:
                        break
            except Exception:
                logger.warning("跳过无法读取的片段: %s", clip_path.name)

        if not selected:
            raise ValueError("未找到可用的视频片段")
        return selected

    # ── 主流程 ────────────────────────────────────────

    def assemble(
        self,
        audio_path: Path,
        output_path: Path,
        start_index: int = 0,
    ) -> Path:
        """拼接背景片段并叠加音频。

        Args:
            audio_path: 音频文件路径（mp3）。
            output_path: 输出 mp4 路径。
            start_index: 从第几个背景片段开始（0=第一个）。
        """
        if not audio_path.exists():
            raise FileNotFoundError(f"音频未找到: {audio_path}")

        audio = AudioFileClip(str(audio_path))
        target_duration = round(audio.duration, 2)
        logger.info("目标音频时长: %.1fs", target_duration)

        clip_paths = self._collect_clips(start_index, target_duration)
        logger.info("已选择 %d 个片段", len(clip_paths))

        clips: list[VideoFileClip] = []
        final = None
        try:
            for clip_path in clip_paths:
                clips.append(VideoFileClip(str(clip_path)))

            fps = min(clips[0].fps or 30, 24)
            logger.info("输出帧率: %d", fps)

            final = concatenate_videoclips(clips, method="compose")
            if final.duration > target_duration:
                final = final.subclipped(0, target_duration)

            final = final.with_audio(audio)

            threads = max(1, multiprocessing.cpu_count() // 2)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            logger.info("正在导出视频 (%d 线程) …", threads)
            final.write_videofile(
                str(output_path),
                codec="libx264",
                audio_codec="aac",
                fps=fps,
                preset="ultrafast",
                threads=threads,
            )
            logger.info("视频已保存 → %s", output_path)
            return output_path

        finally:
            if audio:
                audio.close()
            if final:
                final.close()
            for clip in clips:
                try:
                    clip.close()
                except Exception:
                    pass
