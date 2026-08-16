"""小说路由"""

from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.core.paths import PathConfig
from app.schemas.novel import CompileRequest, GenerateRequest
from app.tasks import gen_tasks, novel_tasks

router = APIRouter(prefix="/api/novel", tags=["Novel"])


@router.get("/prompt-template")
async def get_prompt_template() -> dict:
    """返回默认提示词模板，供前端编辑。"""
    try:
        paths = PathConfig.from_settings(settings, theme="")
        content = paths.theme_novel_prompt.read_text(encoding="utf-8")
        return {"data": {"content": content}, "message": "ok"}
    except FileNotFoundError:
        raise HTTPException(500, "提示词模板文件未找到") from None


@router.post("/kernel")
async def start_compile(req: CompileRequest) -> dict:
    """启动叙事内核编译"""
    try:
        task_id = novel_tasks.start_compile(req.theme)
        return {"data": {"task_id": task_id}, "message": "ok"}
    except Exception as e:
        raise HTTPException(500, str(e)) from e


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
        task_id = gen_tasks.start_generation(
            theme=req.theme,
            kernel=req.kernel,
            target_words=req.target_words,
            custom_prompt=req.custom_prompt,
        )
        return {"data": {"task_id": task_id}, "message": "ok"}
    except Exception as e:
        raise HTTPException(500, str(e)) from e


@router.get("/generate/{task_id}")
async def get_generate_status(task_id: str) -> dict:
    """轮询小说生成状态"""
    state = gen_tasks.get_task_status(task_id)
    if not state:
        raise HTTPException(404, "任务不存在")
    return {"data": {"task_id": task_id, **state}, "message": "ok"}
