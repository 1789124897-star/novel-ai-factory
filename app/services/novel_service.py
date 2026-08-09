"""小说服务 — 叙事内核编译"""

import logging
from pathlib import Path

import requests

from app.core.config import settings
from app.core.paths import PathConfig
from app.services.task_manager import TaskManager

logger = logging.getLogger(__name__)

_task_manager = TaskManager()


def start_compile(theme: str) -> str:
    """启动后台内核编译任务，返回 task_id。"""
    task_id = _task_manager.start(_do_compile, theme)
    logger.info("内核编译任务已启动 task_id=%s theme=%s", task_id, theme)
    return task_id


def get_compile_status(task_id: str) -> dict | None:
    """查询编译任务状态。"""
    return _task_manager.get(task_id)


def _do_compile(task_id: str, theme: str) -> None:
    """后台执行内核编译，完成后将结果写入任务状态。"""
    data = compile_kernel(theme)
    _task_manager.update(task_id, **data)


# ── 业务逻辑 ─────────────────────────────────────────────────

def compile_kernel(theme: str) -> dict:
    """编译主题为结构化叙事内核，保存到文件并返回。"""
    paths = PathConfig.from_settings(settings, theme=theme)

    prompt_path = paths.theme_compiler_prompt
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt 模板未找到: {prompt_path}")
        
    template = prompt_path.read_text(encoding="utf-8").strip()
    if not template:
        raise ValueError(f"Prompt 模板为空: {prompt_path}")
    prompt = template.format(theme=theme)

    payload = {
        "model": settings.DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": "你是小说主题与叙事内核设计专家。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": settings.DEEPSEEK_TEMPERATURE,
        "max_tokens": settings.DEEPSEEK_MAX_TOKENS,
    }

    logger.info("正在编译叙事内核，主题：%s", theme)
    response = requests.post(
        settings.DEEPSEEK_BASE_URL,
        headers={
            "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=120,
    )
    response.raise_for_status()
    kernel_text = response.json()["choices"][0]["message"]["content"]

    output_path: Path = paths.kernel_file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(kernel_text, encoding="utf-8")
    logger.info("内核已保存 → %s", output_path)

    return {
        "theme": theme,
        "kernel": kernel_text,
        "kernel_path": str(output_path),
    }
