"""TTS schemas"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TTSRequest(BaseModel):
    """Edge TTS 合成请求。"""

    text: str = Field(min_length=1)
    voice: str = Field(min_length=1, description="edge-tts 音色")
    rate: str = Field(pattern=r"^[+-]\d+%$", description="语速")
