"""TTS schemas"""

from pydantic import BaseModel

DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"
DEFAULT_RATE = "+0%"


class TTSRequest(BaseModel):
    text: str
    voice: str = DEFAULT_VOICE
    rate: str = DEFAULT_RATE
