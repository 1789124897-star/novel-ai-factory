"""novel-ai-factory Web 服务 — FastAPI + 静态前端。"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import novel_router, pipeline_router, tts_router, upload_router, video_router
from app.core.config import settings
from app.core.constants import OUTPUT_URL_PREFIX
from app.core.logging import setup_logging
from app.core.paths import PathConfig

setup_logging(settings)

app = FastAPI(title="小说AI工厂", version="1.0.0")

paths = PathConfig.from_settings(settings, theme="")

# API 路由
app.include_router(novel_router)
app.include_router(tts_router)
app.include_router(upload_router)
app.include_router(video_router)
app.include_router(pipeline_router)

# 静态文件
static_dir = paths.static_dir
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# 输出产物（小说 txt / mp3 / mp4）
output_dir = paths.output
app.mount(OUTPUT_URL_PREFIX, StaticFiles(directory=str(output_dir)), name="output")


@app.get("/")
async def index():
    """返回前端页面。"""
    from fastapi.responses import FileResponse

    return FileResponse(str(static_dir / "index.html"))
