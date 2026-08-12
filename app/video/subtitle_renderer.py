"""Pillow + MoviePy SRT 字幕叠加。"""

import logging
import multiprocessing
from pathlib import Path
from typing import Optional

import numpy as np
from moviepy import CompositeVideoClip, ImageClip, VideoFileClip
from PIL import Image, ImageDraw, ImageFont

from ..core.config import Settings
from ..core.paths import PathConfig

logger = logging.getLogger(__name__)


class SubtitleRenderer:
    """将 SRT 字幕渲染为半透明文字叠加层。"""

    FONT_SIZE = 40
    SUBTITLE_Y_RATIO = 0.3

    def __init__(self, settings: Settings, paths: PathConfig):
        if not paths.font_path.exists():
            raise FileNotFoundError(f"字体未找到: {paths.font_path}")
        self._font = ImageFont.truetype(str(paths.font_path), self.FONT_SIZE)
        self._y_ratio = self.SUBTITLE_Y_RATIO

    # ── SRT 解析 ─────────────────────────────────────
    @staticmethod
    def _time_to_seconds(t: str) -> float:
        h, m, s = t.split(":")
        s, ms = s.split(",")
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

    def _parse_srt(self, srt_path: Path) -> list[tuple[float, float, str]]:
        """解析 SRT 文件"""

        entries: list[tuple[float, float, str]] = []
        for block in srt_path.read_text(encoding="utf-8-sig").strip().split("\n\n"):
            lines = [line.strip() for line in block.split("\n") if line.strip()]
            if len(lines) < 3:
                continue
            try:
                start, end = lines[1].split(" --> ")
                entries.append((self._time_to_seconds(start), self._time_to_seconds(end), " ".join(lines[2:])))
            except (ValueError, IndexError):
                logger.debug("跳过格式异常的 SRT 块")
        logger.info("已解析 %d 条字幕", len(entries))
        return entries

    # ── 文字渲染 ─────────────────────────────────────
    def _wrap_text(self, text: str, max_width: int) -> list[str]:
        """按像素宽度自动换行。"""
        lines: list[str] = []
        current = ""
        for char in text:
            if self._font.getbbox(current + char)[2] > max_width:
                lines.append(current)
                current = char
            else:
                current += char
        if current:
            lines.append(current)
        return lines

    def _render_image(self, text: str, video_width: int) -> np.ndarray:
        """将文字渲染为透明背景的 RGBA 图像。"""
        margin = 80
        max_width = video_width - margin
        lines = self._wrap_text(text, max_width)
        line_height = self._font.getbbox("测")[3] + 15
        height = line_height * len(lines) + 20

        img = Image.new("RGBA", (video_width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        y = 10
        for line in lines:
            w = self._font.getbbox(line)[2]
            x = (video_width - w) // 2
            draw.text(
                (x, y),
                line,
                font=self._font,
                fill="white",
            )
            y += line_height
        return np.array(img)

    # ── 渲染 ─────────────────────────────────────────

    def build_sub_clips(self, srt_path: Path, video_size: tuple[int, int]) -> list[ImageClip]:
        """解析 SRT 并返回 ImageClip 列表"""
        
        entries = self._parse_srt(srt_path)
        video_width, video_height = video_size
        sub_clips: list[ImageClip] = []
        for i, (start, end, text) in enumerate(entries, 1):
            img = self._render_image(text, video_width)
            clip = ImageClip(img).with_start(start).with_end(end).with_position(
                ("center", video_height * self._y_ratio)
            )
            sub_clips.append(clip)
            if i % 50 == 0:
                logger.info("  字幕 %d/%d", i, len(entries))
        return sub_clips

    def render(self, video_path: Path, srt_path: Path, output_path: Path) -> Path:
        """加载视频 + 解析 SRT → 叠加字幕 → 写出。"""
        if not video_path.exists():
            raise FileNotFoundError(f"视频未找到: {video_path}")
        if not srt_path.exists():
            raise FileNotFoundError(f"SRT 未找到: {srt_path}")

        logger.info("正在加载视频 …")
        video = VideoFileClip(str(video_path))
        logger.info("视频: %dx%d", *video.size)

        sub_clips = self.build_sub_clips(srt_path, video.size)

        final: Optional[CompositeVideoClip] = None
        try:
            final = CompositeVideoClip([video, *sub_clips], size=video.size)
            threads = min(8, multiprocessing.cpu_count())
            output_path.parent.mkdir(parents=True, exist_ok=True)
            final.write_videofile(
                str(output_path),
                codec="libx264",
                audio_codec="aac",
                fps=video.fps,
                preset="fast",
                threads=threads,
                bitrate="5000k",
            )
            logger.info("已加字幕视频 → %s", output_path)
            return output_path
        finally:
            video.close()
            for sub_clip in sub_clips:
                sub_clip.close()
            if final:
                final.close()
