"""应用配置 — 从 .env 加载"""

from pathlib import Path

from pydantic import PositiveFloat, field_validator
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
    DEEPSEEK_API_KEY: str  # 必填
    DEEPSEEK_BASE_URL: str  # 必填

    DEEPSEEK_MODEL: str = "deepseek-v4-pro"

    DEEPSEEK_TEMPERATURE: float = 0.85
    DEEPSEEK_TOP_P: float = 0.92
    DEEPSEEK_MAX_TOKENS: int = 12000

    DEEPSEEK_PRESENCE_PENALTY: float = 0.4
    DEEPSEEK_FREQUENCY_PENALTY: float = 0.2

    # ── TTS ────────────────────────────────────────────────
    TENCENT_SECRET_ID: str  # 必填
    TENCENT_SECRET_KEY: str  # 必填
    TENCENT_REGION: str = "ap-guangzhou"

    TTS_VOICE_ID: int = 601000
    TTS_SPEED: int = 0
    TTS_VOLUME: int = 5
    TTS_SAMPLE_RATE: int = 24000
    TTS_CODEC: str = "mp3"

    BGM_VOLUME_RATIO: PositiveFloat = 0.3

    # ── 文本分割 ───────────────────────────────────────────
    MAX_SEGMENT_LENGTH: int = 140
    MIN_HOPE_LENGTH: int = 55
    MIN_FORCE_MERGE_LENGTH: int = 35

    SLEEP_BETWEEN_REQUESTS: PositiveFloat = 0.2

    STRONG_END: str = r"[。？！…～]"
    MEDIUM_SPLIT: str = r"[；：—━]"
    WEAK_SPLIT: str = r"[，、]"

    # ── 爬虫 / 字幕 ────────────────────────────────────────
    TARGET_URL: str  # 必填 — TurboScribe 地址
    BROWSER_PATH: Path  # 必填 — Chromium/Edge 可执行文件路径

    HEADLESS: bool = False
    TIMEOUT: int = 120
    POLL_INTERVAL: float = 1.0

    # ── 水印 ────────────────────────────────────────────────
    WATERMARK_AUTHOR: str = "@作者"
    WATERMARK_FONT: Path = Path("assets/fonts/Z-SIMHEI.TTF")

    # ════════════════════════════════════════════════════════
    #  字段校验
    # ════════════════════════════════════════════════════════

    @field_validator("TTS_SPEED")
    @classmethod
    def _validate_speed(cls, v: int) -> int:
        if not -2 <= v <= 6:
            raise ValueError("TTS_SPEED must be between -2 and 6")
        return v

    @field_validator("TTS_VOLUME")
    @classmethod
    def _validate_volume(cls, v: int) -> int:
        if not 0 <= v <= 10:
            raise ValueError("TTS_VOLUME must be between 0 and 10")
        return v

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

    @field_validator("DEEPSEEK_TOP_P")
    @classmethod
    def _check_top_p(cls, v: float) -> float:
        if not 0 <= v <= 1:
            raise ValueError("DEEPSEEK_TOP_P must be between 0 and 1")
        return v

    @field_validator("DEEPSEEK_FREQUENCY_PENALTY", "DEEPSEEK_PRESENCE_PENALTY")
    @classmethod
    def _check_penalty(cls, v: float) -> float:
        if not -2 <= v <= 2:
            raise ValueError("Penalty 参数必须在 -2 到 2 之间")
        return v


settings = Settings()
