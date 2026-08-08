"""小说路由"""

from fastapi import APIRouter

from app.schemas.novel import CompileRequest
from app.services.novel_service import NovelService

router = APIRouter(prefix="/api", tags=["Novel"])


@router.post("/kernel")
async def compile_kernel(req: CompileRequest) -> dict:
    """编译叙事内核"""
    try:
        data = NovelService.compile_kernel(req.theme)
        return {"data": data, "message": "ok"}
    except Exception as e:
        return {"data": None, "message": str(e)}
