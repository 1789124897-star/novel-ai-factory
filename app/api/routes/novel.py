"""小说路由"""

from fastapi import APIRouter, HTTPException

from app.schemas.novel import CompileRequest, GenerateRequest
from app.tasks import novel_tasks, gen_tasks

router = APIRouter(prefix="/api/novel", tags=["Novel"])


@router.post("/kernel")
async def start_compile(req: CompileRequest) -> dict:
    """启动叙事内核编译"""
    try:
        task_id = novel_tasks.start_compile(req.theme)
        return {"data": {"task_id": task_id}, "message": "ok"}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/kernel/{task_id}")
async def get_compile_status(task_id: str) -> dict:
    """轮询内核编译状态"""
    state = novel_tasks.get_compile_status(task_id)
    if not state:
        raise HTTPException(404, "任务不存在")
    return {"data": {"task_id": task_id, **state}, "message": "ok"}


@router.post("/generate")
async def start_generate(req: GenerateRequest) -> dict:
    """启动四阶段小说生成"""
    try:
        task_id = gen_tasks.start_generation(req.theme, req.kernel)
        return {"data": {"task_id": task_id}, "message": "ok"}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/generate/{task_id}")
async def get_generate_status(task_id: str) -> dict:
    """轮询小说生成状态"""
    state = gen_tasks.get_task_status(task_id)
    if not state:
        raise HTTPException(404, "任务不存在")
    return {"data": {"task_id": task_id, **state}, "message": "ok"}
