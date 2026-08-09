"""使用 Pillow + MoviePy 将 SRT 字幕叠加到视频上。"""

from __future__ import annotations

import logging
import multiprocessing
from pathlib import Path

import numpy as np
from moviepy import CompositeVideoClip, ImageClip, VideoFileClip
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


class SubtitleRenderer:
    """将 SRT 字幕渲染为半透明文字叠加层。"""

    def __init__(
        self,
        font_path: Path,
        font_size: int = 40,
        stroke_width: int = 2,
        subtitle_y_ratio: float = 0.3,
    ):
        if not font_path.exists():
            raise FileNotFoundError(f"Font not found: {font_path}")
        self.font_path = str(font_path)
        self.font_size = font_size
        self.stroke_width = stroke_width
        self._y_ratio = subtitle_y_ratio
        self._font = ImageFont.truetype(self.font_path, font_size)
        self._video: VideoFileClip | None = None
        self._sub_clips: list[ImageClip] = []

    # ── SRT 解析 ──────────────────────────────────────

    @staticmethod
    def _time_to_seconds(t: str) -> float:
        h, m, s = t.split(":")
        s, ms = s.split(",")
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

    def _parse_srt(self, srt_path: Path) -> list[tuple[float, float, str]]:
        content = srt_path.read_text(encoding="utf-8-sig")
        subtitles = []
        for block in content.strip().split("\n\n"):
            lines = [line.strip() for line in block.split("\n") if line.strip()]
            if len(lines) < 3:
                continue
            try:
                start, end = lines[1].split(" --> ")
                text = " ".join(lines[2:])
                subtitles.append(
                    (self._time_to_seconds(start), self._time_to_seconds(end), text)
                )
            except (ValueError, IndexError):
                logger.debug("跳过格式异常的 SRT 块")
                continue
        logger.info("已解析 %d 条字幕", len(subtitles))
        return subtitles

    # ── 文字渲染 ──────────────────────────────────────

    def _wrap_text(self, text: str, max_width: int) -> list[str]:
        lines = []
        current = ""
        for char in text:
            bbox = self._font.getbbox(current + char)
            if bbox[2] > max_width:
                lines.append(current)
                current = char
            else:
                current += char
        if current:
            lines.append(current)
        return lines

    def _render_image(self, text: str, video_width: int) -> np.ndarray:
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
                stroke_width=self.stroke_width,
                stroke_fill="black",
            )
            y += line_height
        return np.array(img)

    # ── 渲染 ──────────────────────────────────────────

    def render(self, video_path: Path, srt_path: Path, output_path: Path) -> Path:
        if not video_path.exists():
            raise FileNotFoundError(f"视频未找到: {video_path}")
        if not srt_path.exists():
            raise FileNotFoundError(f"SRT 未找到: {srt_path}")

        logger.info("正在加载视频 …")
        self._video = VideoFileClip(str(video_path))
        video_width, video_height = self._video.size
        logger.info("视频: %dx%d", video_width, video_height)

        entries = self._parse_srt(srt_path)
        for i, (start, end, text) in enumerate(entries, 1):
            img = self._render_image(text, video_width)
            clip = ImageClip(img).with_start(start).with_end(end).with_position(
                ("center", video_height * self._y_ratio)
            )
            self._sub_clips.append(clip)
            if i % 50 == 0:
                logger.info("  字幕 %d/%d", i, len(entries))

        final = CompositeVideoClip(
            [self._video, *self._sub_clips], size=self._video.size
        )
        threads = min(8, multiprocessing.cpu_count())
        output_path.parent.mkdir(parents=True, exist_ok=True)
        final.write_videofile(
            str(output_path),
            codec="libx264",
            audio_codec="aac",
            fps=self._video.fps,
            preset="fast",
            threads=threads,
            bitrate="5000k",
        )
        self._cleanup()
        logger.info("已加字幕视频 → %s", output_path)
        return output_path

    def _cleanup(self) -> None:
        if self._video:
            self._video.close()
        for sub_clip in self._sub_clips:
            sub_clip.close()
        self._sub_clips.clear()
