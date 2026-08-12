"""全流程路径清单。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import Settings


@dataclass(frozen=True)
class PathConfig:

    base_root: Path
    settings: Settings
    _theme: str

    @classmethod
    def from_settings(cls, settings: Settings, theme: str) -> PathConfig:
        """按主题构建路径配置，输出根目录取自 settings.OUTPUT_DIR。"""
        return cls(base_root=Path(settings.OUTPUT_DIR), settings=settings, _theme=theme)

    # ── 工具 ───────────────────────────────────────────────

    @staticmethod
    def _ensure(path: Path) -> Path:
        """创建目录"""
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def project_root(self) -> Path:
        """项目根目录"""
        return Path(__file__).resolve().parents[2]

    @property
    def theme(self) -> str:
        """清洗后的主题名，用于目录与文件名。"""
        raw = self._theme.strip()
        return raw.replace("/", "_").replace("\\", "_")

    # ── 输出根 ─────────────────────────────────────────────

    @property
    def output(self) -> Path:
        """输出根目录（自动创建）。"""
        return self._ensure(self.base_root)

    # ── 小说 ───────────────────────────────────────────────

    @property
    def novel_dir(self) -> Path:
        """当前主题的小说目录（按《主题名》命名，自动创建）。"""
        return self._ensure(self.output / "novel" / f"《{self.theme}》")

    @property
    def kernel_file(self) -> Path:
        """叙事内核文件。"""
        return self.novel_dir / "00_叙事内核.txt"

    def part_file(self, round_num: int) -> Path:
        """第 round_num 阶段生成的小说正文文件。"""
        return self.novel_dir / f"part_{round_num:02d}.txt"

    @property
    def novel_output(self) -> Path:
        """四阶段合并后的完整小说文件。"""
        return self.novel_dir / f"《{self.theme}》.txt"

    # ── 资源 ───────────────────────────────────────────────

    @property
    def assets_dir(self) -> Path:
        """静态资源根目录。"""
        return self.project_root / "assets"

    @property
    def video_clip_dir(self) -> Path:
        """背景视频片段目录。"""
        return self.assets_dir / "videos"

    @property
    def bgm_path(self) -> Path:
        """默认背景音乐文件。"""
        return self.assets_dir / "bgm" / "bgm.mp3"

    @property
    def font_path(self) -> Path:
        """字幕和水印使用的主字体。"""
        font_file = Path(self.settings.WATERMARK_FONT)
        if not font_file.is_absolute():
            font_file = self.project_root / font_file
        return font_file

    # ── 视频与 TTS ─────────────────────────────────────────

    @property
    def video_output(self) -> Path:
        """视频产物目录（自动创建）。"""
        return self._ensure(self.output / "video")

    @property
    def tts_output(self) -> Path:
        """TTS 配音产物目录（自动创建）。"""
        return self._ensure(self.output / "tts")

    @property
    def prompts_dir(self) -> Path:
        """提示词模板目录。"""
        return self.project_root / "prompts"

    @property
    def theme_compiler_prompt(self) -> Path:
        """叙事内核编译模板文件。"""
        return self.prompts_dir / "theme_compiler.txt"

    @property
    def theme_novel_prompt(self) -> Path:
        """小说生成模板文件。"""
        return self.prompts_dir / "novel_prompt.txt"
