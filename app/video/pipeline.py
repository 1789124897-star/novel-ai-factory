"""视频拼接 — 背景片段串连 + 音频叠加。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from moviepy import (
    AudioFileClip,
    VideoFileClip,
    concatenate_videoclips,
)

from ..core.config import Settings
from ..core.constants import VIDEO_ALLOWED_EXTENSIONS
from ..core.paths import PathConfig

logger = logging.getLogger(__name__)


class VideoPipeline:
    """选择背景片段，拼接并叠加音频。"""

    def __init__(self, settings: Settings, paths: PathConfig):
        self._settings = settings
        self._paths = paths

    # 默认视频素材收集
    def _collect_clips(self, start_index: int, target_duration: float) -> list[Path]:

        # 排列视频路径
        all_clips = sorted(clip_path for clip_path in self._paths.video_clip_dir.iterdir() if clip_path.suffix.lower() in VIDEO_ALLOWED_EXTENSIONS)
        if not all_clips:
            raise FileNotFoundError(f"{self._paths.video_clip_dir} 中未找到视频片段")

        selected: list[Path] = []  # 已选中的片段路径
        accumulated = 0.0  # 累计时长

        for i in range(len(all_clips) * 10):
            clip_path = all_clips[(start_index + i) % len(all_clips)]
            try:
                with VideoFileClip(str(clip_path)) as clip:
                    if clip.duration <= 0:
                        continue
                    selected.append(clip_path)
                    accumulated += clip.duration
                    logger.info("[%d] %s  时长=%.1f秒  累计=%.1f秒", len(selected), clip_path.name, clip.duration, accumulated)
            except Exception:
                logger.warning("跳过无法读取的片段: %s", clip_path.name)
            if accumulated >= target_duration:
                break

        if not selected:
            raise ValueError("未找到可用的视频片段")
        return selected

    # 主流程
    def assemble(
        self,
        audio_path: Path,
        start_index: int = 0,
        video_paths: Optional[list[Path]] = None,
    ) -> VideoFileClip:
        """拼接背景片段并叠加音频"""

        if not audio_path.exists():
            raise FileNotFoundError(f"音频未找到: {audio_path}")
        audio = AudioFileClip(str(audio_path))
        target_duration = round(audio.duration, 2)
        logger.info("目标音频时长: %.1fs", target_duration)

        video_paths = [p for p in video_paths if p.exists()] if video_paths else self._collect_clips(start_index, target_duration)
        if not video_paths:
            raise FileNotFoundError("指定的背景视频均不可用")
        logger.info("已选择 %d 个片段", len(video_paths))

        clips: list[VideoFileClip] = []
        final = None
        try:
            for clip_path in video_paths:
                clips.append(VideoFileClip(str(clip_path)))

            final = concatenate_videoclips(clips, method="compose")
            if final.duration > target_duration:
                final = final.subclipped(0, target_duration)
            final = final.with_audio(audio)
            return final
        except Exception:
            audio.close()
            if final:
                final.close()
            for clip in clips:
                try:
                    clip.close()
                except Exception:
                    pass
            raise
