"""可配置的 FFmpeg drawtext 水印叠加。"""

import logging
import math
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..core.config import Settings
    from ..core.paths import PathConfig

logger = logging.getLogger(__name__)


def _escape_ffmpeg_text(text: str) -> str:
    """转义 FFmpeg drawtext 过滤器值中的特殊字符。"""
    return text.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:").replace("%", "\\%")


class Watermark:
    """通过 FFmpeg drawtext 过滤器叠加多层文字水印。"""

    FFMPEG_TIMEOUT = 300  # 秒

    def __init__(self, settings: "Settings", paths: "PathConfig"):
        self._settings = settings
        self._paths = paths

    # ── 工具 ──────────────────────────────────────────

    @staticmethod
    def _audio_duration_minutes(audio_path: Path) -> int:
        """通过 ffprobe 获取音频向上取整的分钟数（避免完整解码）。"""
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(audio_path),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                seconds = float(result.stdout.strip())
                return math.ceil(seconds / 60)
        except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
            logger.warning("ffprobe 失败 — 降级使用 pydub")
        # 降级
        from pydub import AudioSegment  # noqa: PLC0415
        audio = AudioSegment.from_file(audio_path)
        return math.ceil(len(audio) / 1000 / 60)

    def _drawtext(
        self, text: str, size: int, color: str, x: str, y: str, alpha: float = 1.0
    ) -> str:
        color_spec = f"{color}@{alpha}" if alpha < 1.0 else color
        font = _escape_ffmpeg_text(str(self._paths.font_path))
        text_safe = _escape_ffmpeg_text(text)
        return (
            f"drawtext=fontfile='{font}':text='{text_safe}':"
            f"fontsize={size}:fontcolor={color_spec}:x={x}:y={y}"
        )

    # ── 主入口 ────────────────────────────────────────

    def apply(
        self,
        input_path: Path,
        output_path: Path,
        *,
        author: str = "",
        theme: str = "",
        audio_path: Optional[Path] = None,
    ) -> Path:
        """叠加多层文字水印。

        Args:
            input_path: 输入视频路径。
            output_path: 输出视频路径。
            author: 署名文字（空则从配置读取）。
            theme: 书名标题（空则从路径推断）。
            audio_path: 用于计算时长的音频（空则跳过时长行）。
        """
        if not input_path.exists():
            raise FileNotFoundError(f"输入视频未找到: {input_path}")

        author = author or self._settings.WATERMARK_AUTHOR
        if not theme:
            theme = self._paths.theme

        # 书名 + 作者
        filters = [
            self._drawtext(
                f"《 {theme} 》", 90, "0x791E1E", "(w-text_w)/2", "80"
            ),
        ]

        # 时长行（需要音频）
        if audio_path and audio_path.exists():
            minutes = self._audio_duration_minutes(audio_path)
            filters.append(self._drawtext(
                f"全文{minutes}分钟", 60, "0x000000", "(w-text_w)/2", "180"
            ))

        filters.extend([
            self._drawtext("已完结", 60, "0x000000", "(w-text_w)/2", "250"),
            self._drawtext(
                "小说纯属虚构 请勿模仿",
                50, "0x000000", "(w-text_w)/2", "(h-80-text_h)",
            ),
            self._drawtext(
                author, 50, "0x87CEFA", "(w-40-text_w)", "(h-200-text_h)", alpha=0.5,
            ),
        ])

        filter_chain = ",".join(filters)
        cmd = [
            "ffmpeg",
            "-i",
            str(input_path),
            "-vf",
            filter_chain,
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "23",
            "-c:a",
            "copy",
            "-y",
            str(output_path),
        ]

        logger.info("正在添加水印 …")
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=self.FFMPEG_TIMEOUT
        )
        if result.returncode != 0:
            logger.error("FFmpeg 失败:\n%s", result.stderr)
            raise subprocess.CalledProcessError(
                result.returncode, cmd, result.stdout, result.stderr
            )
        logger.info("已加水印 → %s", output_path)
        return output_path
