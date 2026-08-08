"""全流程路径清单。

``PathConfig`` 是只读（frozen）数据类，从 ``Settings`` 派生所有产物路径。
目录按需创建，不在构造时提前建。
"""

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Settings


@dataclass(frozen=True)
class PathConfig:
    """从 ``Settings`` 派生所有输出和资源路径。"""

    base_root: Path
    settings: "Settings"
    _theme: str = ""

    # ── 工厂方法 ───────────────────────────────────────────

    @classmethod
    def from_settings(cls, settings: "Settings", theme: str = "") -> "PathConfig":
        return cls(base_root=Path(settings.OUTPUT_DIR), settings=settings, _theme=theme)

    # ── 工具 ───────────────────────────────────────────────

    @staticmethod
    def _ensure(path: Path) -> Path:
        """创建目录（含父级），若不存在则返回路径。"""
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def project_root(self) -> Path:
        """项目根目录（``pyproject.toml`` 所在位置）。"""
        return Path(__file__).resolve().parents[2]

    @property
    def theme(self) -> str:
        """清洗后的主题名，用于目录命名。"""
        raw = self._theme.strip()
        return raw.replace("/", "_").replace("\\", "_")

    # ══════════════════════════════════════════════════════════
    #  输出根
    # ══════════════════════════════════════════════════════════

    @property
    def output(self) -> Path:
        return self._ensure(self.base_root)

    # ══════════════════════════════════════════════════════════
    #  小说
    # ══════════════════════════════════════════════════════════

    @property
    def novel_dir(self) -> Path:
        return self._ensure(self.output / "novel" / f"《{self.theme}》")

    @property
    def kernel_file(self) -> Path:
        return self.novel_dir / "00_叙事内核.txt"

    @property
    def history_file(self) -> Path:
        return self.novel_dir / "history_messages.json"

    def part_file(self, round_num: int) -> Path:
        return self.novel_dir / f"part_{round_num:02d}.txt"

    @property
    def novel_output(self) -> Path:
        return self.novel_dir / f"《{self.theme}》.txt"

    # ══════════════════════════════════════════════════════════
    #  TTS
    # ══════════════════════════════════════════════════════════

    @property
    def tts_dir(self) -> Path:
        return self._ensure(self.output / "tts" / f"《{self.theme}》")

    @property
    def tts_seg_list_dir(self) -> Path:
        return self._ensure(self.tts_dir / "seg_list")

    @property
    def preview_file(self) -> Path:
        return self.tts_dir / "tts_preview.txt"

    @property
    def failed_file(self) -> Path:
        return self.tts_dir / "failed_segments.txt"

    @property
    def merged_audio(self) -> Path:
        return self.tts_dir / "merged.mp3"

    @property
    def final_mixed_audio(self) -> Path:
        return self.tts_dir / "final_with_bgm.mp3"

    # ══════════════════════════════════════════════════════════
    #  字幕 / 爬虫
    # ══════════════════════════════════════════════════════════

    @property
    def crawler_dir(self) -> Path:
        return self._ensure(self.output / "crawler" / f"《{self.theme}》")

    @property
    def crawler_unprocessed_srt(self) -> Path:
        return self.crawler_dir / "unprocessed.srt"

    @property
    def crawler_cleaned_srt(self) -> Path:
        return self.crawler_dir / "cleaned.srt"

    # ══════════════════════════════════════════════════════════
    #  视频
    # ══════════════════════════════════════════════════════════

    @property
    def video_dir(self) -> Path:
        return self._ensure(self.output / "video" / f"《{self.theme}》")

    @property
    def video_with_bgm(self) -> Path:
        return self.video_dir / "video_bgm.mp4"

    @property
    def video_with_srt(self) -> Path:
        return self.video_dir / "video_bgm_srt.mp4"

    @property
    def video_with_watermark(self) -> Path:
        return self.video_dir / "video_with_watermark.mp4"

    # ══════════════════════════════════════════════════════════
    #  资源
    # ══════════════════════════════════════════════════════════

    @property
    def assets_dir(self) -> Path:
        return self.project_root / "assets"

    @property
    def video_clip_dir(self) -> Path:
        """背景视频片段目录。"""
        return self.assets_dir / "videos"

    @property
    def bgm_path(self) -> Path:
        return self.assets_dir / "bgm" / "bgm.mp3"

    @property
    def font_path(self) -> Path:
        """字幕和水印使用的主字体。

        返回配置的 ``WATERMARK_FONT`` 路径。若为相对路径则基于 ``project_root`` 解析。
        """
        p = Path(self.settings.WATERMARK_FONT)
        if not p.is_absolute():
            p = self.project_root / p
        return p

    @property
    def cover_dir(self) -> Path:
        return self.assets_dir / "covers"

    @property
    def prompts_dir(self) -> Path:
        return self.project_root / "prompts"

    @property
    def theme_compiler_prompt(self) -> Path:
        return self.prompts_dir / "theme_compiler.txt"

    @property
    def theme_novel_prompt(self) -> Path:
        return self.prompts_dir / "novel_prompt.txt"
