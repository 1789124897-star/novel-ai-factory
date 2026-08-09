"""小说路由"""

from fastapi import APIRouter, HTTPException

from app.schemas.novel import CompileRequest, GenerateRequest
from app.services import novel_service, novel_gen_service

router = APIRouter(prefix="/api/novel", tags=["Novel"])


@router.post("/kernel")
async def start_compile(req: CompileRequest) -> dict:
    """启动叙事内核编译"""
    try:
        task_id = novel_service.start_compile(req.theme)
        return {"data": {"task_id": task_id}, "message": "ok"}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/kernel/{task_id}")
async def get_compile_status(task_id: str) -> dict:
    """轮询内核编译状态"""
    state = novel_service.get_compile_status(task_id)
    if not state:
        raise HTTPException(404, "任务不存在")
    return {"data": {"task_id": task_id, **state}, "message": "ok"}


@router.post("/generate")
async def start_generate(req: GenerateRequest) -> dict:
    """启动四阶段小说生成"""
    try:
        task_id = novel_gen_service.start_generation(req.theme, req.kernel)
        return {"data": {"task_id": task_id}, "message": "ok"}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/generate/{task_id}")
async def get_generate_status(task_id: str) -> dict:
    """轮询小说生成状态"""
    state = novel_gen_service.get_task_status(task_id)
    if not state:
        raise HTTPException(404, "任务不存在")
    return {"data": {"task_id": task_id, **state}, "message": "ok"}
