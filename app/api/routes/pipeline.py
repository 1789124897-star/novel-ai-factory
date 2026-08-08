"""管道路由 — 薄层，逻辑在 app.services.pipeline_service"""

from fastapi import APIRouter, HTTPException

from app.schemas.pipeline import RunRequest
from app.services.pipeline_service import PipelineService

router = APIRouter(prefix="/api", tags=["Pipeline"])

_service = PipelineService()


# ── 路由 ──────────────────────────────────────────────────────


@router.post("/pipeline/run")
async def run_pipeline(req: RunRequest) -> dict:
    task_id = _service.start(req.theme, target_words=req.target_words)
    return {"data": {"task_id": task_id}, "message": "ok"}


@router.get("/pipeline/{task_id}")
async def get_pipeline_status(task_id: str) -> dict:
    state = _service.get_status(task_id)
    if not state:
        raise HTTPException(404, "任务不存在")

    return {
        "data": {
            "task_id": state.task_id,
            "status": state.status,
            "progress": state.progress,
            "stage": state.stage,
            "theme": state.theme,
            "result": state.result,
            "error": state.error,
        },
        "message": "ok",
    }
