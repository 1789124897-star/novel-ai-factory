"""小说路由"""

from fastapi import APIRouter, HTTPException

from app.schemas.novel import CompileRequest, GenerateRequest
from app.services.novel_service import NovelService
from app.services import novel_gen_service

router = APIRouter(prefix="/api", tags=["Novel"])


@router.post("/kernel")
async def compile_kernel(req: CompileRequest) -> dict:
    """编译叙事内核"""
    try:
        data = NovelService.compile_kernel(req.theme)
        return {"data": data, "message": "ok"}
    except Exception as e:
        return {"data": None, "message": str(e)}


@router.post("/novel/generate")
async def start_generate(req: GenerateRequest) -> dict:
    """启动四阶段小说生成"""
    try:
        task_id = novel_gen_service.start_generation(req.theme, req.kernel)
        return {"data": {"task_id": task_id}, "message": "ok"}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/novel/generate/{task_id}")
async def get_generate_status(task_id: str) -> dict:
    """轮询小说生成状态"""
    state = novel_gen_service.get_task_status(task_id)
    if not state:
        raise HTTPException(404, "任务不存在")
    return {"data": {"task_id": task_id, **state}, "message": "ok"}
