"""MoviePy + Pillow 水印叠加。"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

import numpy as np
from moviepy import AudioFileClip, ImageClip
from PIL import Image, ImageDraw, ImageFont

from ..core.config import Settings
from ..core.paths import PathConfig


class Watermark:
    """叠加多层文字水印。"""

    def __init__(self, settings: Settings, paths: PathConfig):
        self._settings = settings
        self._paths = paths

    # ── 工具 ─────────────────────────────────────────

    @staticmethod
    def _audio_duration_minutes(audio_path: Path) -> int:
        """获取音频向上取整的分钟数。"""
        audio = AudioFileClip(str(audio_path))
        try:
            return math.ceil(audio.duration / 60)
        finally:
            audio.close()

    def _render_text(self, text: str, font_size: int, color: str, alpha: float = 1.0) -> np.ndarray:
        """渲染单行文字为 RGBA numpy 数组。"""
        font = ImageFont.truetype(str(self._paths.font_path), font_size)
        left, top, right, bottom = font.getbbox(text)

        r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
        fill = (r, g, b, int(255 * alpha))

        pad = 10
        img = Image.new("RGBA", (right - left + pad, bottom - top + pad), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.text((pad // 2 - left, pad // 2 - top), text, font=font, fill=fill)
        return np.array(img)

    def _overlay(self, text: str, font_size: int, color: str, position: tuple, alpha: float = 1.0) -> ImageClip:
        """渲染文字并返回定位好的 ImageClip。"""
        img = self._render_text(text, font_size, color, alpha)
        return ImageClip(img).with_position(position)

    # ── 构建叠加层 ───────────────────────────────────

    def build_overlay_clips(
        self,
        video_size: tuple[int, int],
        duration: float,
        *,
        author: str = "",
        theme: str = "",
        audio_path: Optional[Path] = None,
    ) -> list[ImageClip]:
        """返回水印 ImageClip"""
        width, height = video_size
        if not theme:
            theme = self._paths.theme

        # 字号与边距随视频尺寸等比缩放（1080p 基准）
        scale = width / 1080
        big_font = int(64 * scale)
        small_font = int(38 * scale)
        margin = int(30 * scale)

        # 书名（顶部居中，半透明白）
        clips: list[ImageClip] = []
        if theme:
            clips.append(self._overlay(f"《 {theme} 》", big_font, "#FFFFFF", ("center", margin), alpha=0.85))

        # 时长行
        if audio_path and audio_path.exists():
            minutes = self._audio_duration_minutes(audio_path)
            clips.append(self._overlay(f"全文{minutes}分钟", small_font, "#FFFFFF", ("center", margin * 2 + big_font), alpha=0.7))

        # 已完结
        clips.append(self._overlay("已完结", small_font, "#FFFFFF", ("center", margin * 3 + big_font + small_font), alpha=0.7))

        # 免责声明（底部居中，半透明白）
        img = self._render_text("小说纯属虚构 请勿模仿", small_font, "#FFFFFF", alpha=0.5)
        clips.append(ImageClip(img).with_position(("center", height - img.shape[0] - margin)))

        # 作者署名（右下角，半透明白）
        if author:
            img = self._render_text(author, small_font, "#FFFFFF", alpha=0.5)
            clips.append(ImageClip(img).with_position((width - img.shape[1] - margin, height - img.shape[0] - margin * 2)))

        # 水印全程常驻：统一明确结束时间（否则 CompositeVideoClip 无法推断时长）
        return [clip.with_end(duration) for clip in clips]
