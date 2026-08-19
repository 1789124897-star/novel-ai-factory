"""全流程路径清单。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import Settings


def _resolve(path: Path) -> Path:
    """相对路径拼项目根，绝对路径原样返回。"""
    if path.is_absolute():
        return path
    return Path(__file__).resolve().parents[2] / path


@dataclass(frozen=True)
class PathConfig:

    output_root: Path
    font_path: Path
    _theme: str

    @classmethod
    def from_settings(cls, settings: Settings, theme: str) -> PathConfig:
        return cls(
            output_root=_resolve(settings.OUTPUT_DIR),
            font_path=_resolve(settings.WATERMARK_FONT),
            _theme=theme,
        )

    # ── 工具 ───────────────────────────────────────────────

    @staticmethod
    def _ensure_dir(path: Path) -> Path:
        """创建目录"""
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def project_root(self) -> Path:
        """项目根目录"""
        return Path(__file__).resolve().parents[2]

    @property
    def static_dir(self) -> Path:
        """前端静态资源目录"""
        return self.project_root / "static"

    @property
    def theme(self) -> str:
        """清洗后的主题名，用于目录与文件名。"""
        raw = self._theme.strip()
        return raw.replace("/", "_").replace("\\", "_")

    # ── 输出根 ─────────────────────────────────────────────

    @property
    def output(self) -> Path:
        """输出根目录"""
        return self._ensure_dir(self.output_root)

    @property
    def staging_dir(self) -> Path:
        """上传文件暂存目录"""
        return self._ensure_dir(self.output / "_staging")

    def video_task_upload_dir(self, task_id: str) -> Path:
        """指定视频任务的上传文件目录（有文件搬入时才创建）"""
        return self.video_output / task_id / "_uploads"

    # ── 小说 ───────────────────────────────────────────────

    @property
    def novel_dir(self) -> Path:
        """当前主题的小说目录（《主题名》）。"""
        return self._ensure_dir(self.output / "novel" / f"《{self.theme}》")

    @property
    def kernel_file(self) -> Path:
        """叙事内核文件。"""
        return self.novel_dir / "00_叙事内核.txt"

    def part_file(self, round_num: int) -> Path:
        """第 round_num 阶段生成的小说正文文件。"""
        return self.novel_dir / f"part_{round_num:02d}.txt"

    @property
    def novel_final_file(self) -> Path:
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
    def default_bgm_path(self) -> Path:
        """内置默认背景音乐文件。"""
        return self.assets_dir / "bgm" / "bgm.mp3"

    # ── 视频与 TTS ─────────────────────────────────────────

    @property
    def video_output(self) -> Path:
        """视频产物目录。"""
        return self._ensure_dir(self.output / "video")

    def video_task_dir(self, task_id: str) -> Path:
        """指定视频任务的主目录"""
        return self._ensure_dir(self.video_output / task_id)

    def video_task_mixed_audio_file(self, task_id: str) -> Path:
        """视频任务的 BGM 混音产物文件。"""
        return self.video_task_dir(task_id) / "mixed.mp3"

    def video_task_final_video_file(self, task_id: str) -> Path:
        """视频任务的最终产物文件。"""
        return self.video_task_dir(task_id) / "final.mp4"

    @property
    def tts_output(self) -> Path:
        """TTS 配音产物目录。"""
        return self._ensure_dir(self.output / "tts")

    def tts_task_dir(self, task_id: str) -> Path:
        """指定 TTS 任务的产物目录。"""
        return self._ensure_dir(self.tts_output / task_id)

    def tts_voice_file(self, task_id: str) -> Path:
        """指定 TTS 任务的语音产物文件。"""
        return self.tts_task_dir(task_id) / "voice.mp3"

    def tts_subtitle_file(self, task_id: str) -> Path:
        """指定 TTS 任务的字幕产物文件。"""
        return self.tts_task_dir(task_id) / "subtitle.srt"

    @property
    def prompts_dir(self) -> Path:
        """提示词模板目录。"""
        return self.project_root / "prompts"

    @property
    def theme_compiler_prompt(self) -> Path:
        """叙事内核编译模板文件。"""
        return self.prompts_dir / "theme_compiler.txt"

    @property
    def novel_prompt(self) -> Path:
        """小说生成模板文件。"""
        return self.prompts_dir / "novel_prompt.txt"
