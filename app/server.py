"""novel-ai-factory Web 服务 — FastAPI + 静态前端。"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import novel_router, tts_router, video_router
from app.core.config import settings
from app.core.logging import setup_logging

setup_logging(settings)

app = FastAPI(title="小说AI工厂", version="1.0.0")

# API 路由
app.include_router(novel_router)
app.include_router(tts_router)
app.include_router(video_router)

# 静态文件
static_dir = Path(__file__).resolve().parent.parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# 输出产物（小说 txt / mp3 / mp4）
output_dir = Path(__file__).resolve().parent.parent / "output"
output_dir.mkdir(exist_ok=True)
app.mount("/output", StaticFiles(directory=str(output_dir)), name="output")


@app.get("/")
async def index():
    """返回前端页面。"""
    from fastapi.responses import FileResponse

    return FileResponse(str(static_dir / "index.html"))
