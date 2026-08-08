"""API 路由聚合"""

from .novel import router as novel_router
from .pipeline import router as pipeline_router

__all__ = ["novel_router", "pipeline_router"]
