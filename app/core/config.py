"""应用配置。"""

from __future__ import annotations

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全流程统一配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── 日志 ──────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # ── 输出 ───────────────────────────────────────────────
    OUTPUT_DIR: Path = Path("output")

    # ── 小说生成 (DeepSeek) ────────────────────────────────
    DEEPSEEK_API_KEY: str
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1/chat/completions"

    DEEPSEEK_MODEL: str = "deepseek-v4-pro"

    DEEPSEEK_TEMPERATURE: float = 0.85
    DEEPSEEK_MAX_TOKENS: int = 12000

    # ── 视频制作 ───────────────────────────────────────────
    BGM_VOLUME_RATIO: float = 0.3

    # ── 水印 ────────────────────────────────────────────────
    WATERMARK_FONT: Path = Path("assets/fonts/LXGWWenKai-Regular.ttf")

    # ════════════════════════════════════════════════════════
    #  字段校验
    # ════════════════════════════════════════════════════════

    @field_validator("BGM_VOLUME_RATIO")
    @classmethod
    def _validate_bgm_ratio(cls, v: float) -> float:
        return max(0.0, min(1.0, v))

    @field_validator("DEEPSEEK_TEMPERATURE")
    @classmethod
    def _check_temperature(cls, v: float) -> float:
        if not 0 < v < 2:
            raise ValueError("DEEPSEEK_TEMPERATURE must be between 0 and 2")
        return v

    @field_validator("DEEPSEEK_MAX_TOKENS")
    @classmethod
    def _check_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("DEEPSEEK_MAX_TOKENS must be positive")
        return v


settings = Settings()
