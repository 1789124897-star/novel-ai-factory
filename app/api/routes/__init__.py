"""API 路由聚合"""

from .novel import router as novel_router
from .pipeline import router as pipeline_router
from .tts import router as tts_router
from .video import router as video_router

__all__ = ["novel_router", "tts_router", "video_router", "pipeline_router"]
