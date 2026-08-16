"""一键生成 — 全链路编排任务。

把四个独立子任务（内核编译 → 小说生成 → TTS 配音 → 视频合成）
串成一条链：逐个启动、轮询到完成、产物接力给下一步。
编排任务本身也是 TaskManager 任务，产物与阶段信息写入任务状态，
失败后可通过 resume_pipeline 从失败阶段续跑，不重复执行已完成步骤。
"""

import logging
import time
from io import BytesIO
from types import SimpleNamespace
from typing import Optional

from app.services.task_manager import TaskManager
from app.services.video_service import VideoService
from app.tasks import novel_tasks, gen_tasks, tts_tasks, video_tasks

logger = logging.getLogger(__name__)

_task_manager = TaskManager()

_POLL_INTERVAL = 2.0  # 子任务轮询间隔（秒）

# 各子任务默认最长等待时间（秒）
_STAGE_TIMEOUT = {"compile": 300, "generate": 1800, "tts": 900, "video": 3600}

_STAGE_ORDER = ("compile", "generate", "tts", "video")


def _wait_sub_task(task_id: str, getter, timeout: float) -> dict:
    """轮询子任务直到完成，返回最终 state；失败或超时抛异常。"""
    deadline = time.monotonic() + timeout
    while True:
        state = getter(task_id)
        if not state:
            raise RuntimeError("子任务状态不存在")
        if state.get("status") == "done":
            return state
        if state.get("status") == "error":
            raise RuntimeError(f"子任务 {task_id} 失败: {state.get('error') or '未知错误'}")
        if time.monotonic() > deadline:
            raise TimeoutError(f"子任务 {task_id} 执行超时（{timeout:.0f}s）")
        time.sleep(_POLL_INTERVAL)


def _wrap_upload(data: Optional[tuple[str, bytes]]) -> Optional[SimpleNamespace]:
    """把请求阶段读入内存的上传文件包装成 file-like 对象。"""
    if not data:
        return None
    name, content = data
    return SimpleNamespace(filename=name, file=BytesIO(content))


def start_pipeline(
    theme: str,
    target_words: int,
    voice: str,
    rate: str,
    video_source: str,
    bgm_source: str,
    watermark_theme: str,
    watermark_author: str,
    video_files_data: Optional[list[tuple[str, bytes]]] = None,
    bgm_file_data: Optional[tuple[str, bytes]] = None,
) -> str:
    """启动全链路编排任务，返回 task_id。"""
    task_id = _task_manager.start(
        _do_pipeline,
        theme,
        target_words,
        voice,
        rate,
        video_source,
        bgm_source,
        watermark_theme,
        watermark_author,
        video_files_data,
        bgm_file_data,
        "",         # kernel（续跑时复用）
        "",         # novel_text（续跑时复用）
        "",         # tts_task_id（续跑时复用）
        "compile",  # start_stage
    )
    logger.info("编排任务已启动 task_id=%s theme=%s", task_id, theme)
    return task_id


def resume_pipeline(old_task_id: str) -> str:
    """从旧编排任务的失败阶段续跑，复用已完成的产物。"""
    old = _task_manager.get(old_task_id)
    if not old:
        raise RuntimeError("原任务不存在")
    start_stage = old.get("stage") if old.get("stage") in _STAGE_ORDER else "compile"
    task_id = _task_manager.start(
        _do_pipeline,
        old.get("theme", ""),
        old.get("target_words", 8000),
        old.get("voice", "zh-CN-XiaoxiaoNeural"),
        old.get("rate", "+0%"),
        old.get("video_source", "default"),
        old.get("bgm_source", "default"),
        old.get("watermark_theme", ""),
        old.get("watermark_author", ""),
        old.get("video_files_data"),
        old.get("bgm_file_data"),
        old.get("kernel", ""),
        old.get("novel_text", ""),
        old.get("tts_task_id", ""),
        start_stage,
    )
    logger.info("编排任务续跑 task_id=%s 原任务=%s 起始阶段=%s", task_id, old_task_id, start_stage)
    return task_id


def get_pipeline_status(task_id: str) -> Optional[dict]:
    """查询编排任务状态。"""
    return _task_manager.get(task_id)


def _do_pipeline(
    task_id: str,
    theme: str,
    target_words: int,
    voice: str,
    rate: str,
    video_source: str,
    bgm_source: str,
    watermark_theme: str,
    watermark_author: str,
    video_files_data: Optional[list[tuple[str, bytes]]],
    bgm_file_data: Optional[tuple[str, bytes]],
    kernel: str,
    novel_text: str,
    tts_task_id: str,
    start_stage: str,
) -> None:
    """后台执行全链路编排：依次启动子任务并轮询接力。"""
    # 配置写回任务状态，供续跑恢复
    _task_manager.update(
        task_id,
        theme=theme,
        target_words=target_words,
        voice=voice,
        rate=rate,
        video_source=video_source,
        bgm_source=bgm_source,
        watermark_theme=watermark_theme,
        watermark_author=watermark_author,
        video_files_data=video_files_data,
        bgm_file_data=bgm_file_data,
    )

    # ① 编译内核
    if start_stage == "compile":
        _task_manager.update(task_id, stage="compile", stage_label="编译叙事内核")
        kid = novel_tasks.start_compile(theme)
        state = _wait_sub_task(kid, novel_tasks.get_compile_status, _STAGE_TIMEOUT["compile"])
        kernel = state.get("kernel") or ""

    # ② 生成小说
    if start_stage in ("compile", "generate") and not novel_text:
        _task_manager.update(task_id, stage="generate", stage_label="四阶段小说生成", kernel=kernel)
        gid = gen_tasks.start_generation(theme=theme, kernel=kernel, target_words=target_words)
        state = _wait_sub_task(gid, gen_tasks.get_task_status, _STAGE_TIMEOUT["generate"])
        novel_text = "\n\n".join(
            state.get("stages", {}).get(n) or "" for n in ("起", "承", "转", "合")
        ).strip()

    # ③ TTS 配音
    if start_stage in ("compile", "generate", "tts") and not tts_task_id:
        _task_manager.update(task_id, stage="tts", stage_label="TTS 配音", novel_text=novel_text)
        tid = tts_tasks.start_synthesis(text=novel_text, voice=voice, rate=rate)
        tts_state = _wait_sub_task(tid, tts_tasks.get_task_status, _STAGE_TIMEOUT["tts"])
        tts_task_id = tid
        # 产物写回状态：供前端同步分步模块，也供续跑复用
        _task_manager.update(
            task_id,
            tts_task_id=tts_task_id,
            tts_audio_url=tts_state.get("audio_url", ""),
            tts_srt_url=tts_state.get("srt_url", ""),
            novel_text=novel_text,
        )

    # ④ 视频合成
    _task_manager.update(task_id, stage="video", stage_label="视频合成", tts_task_id=tts_task_id)
    vid = VideoService.start_video_task(
        audio_source="tts",
        audio_tts_task_id=tts_task_id,
        srt_source="tts",
        srt_tts_task_id=tts_task_id,
        video_source=video_source,
        bgm_source=bgm_source,
        theme=watermark_theme,
        watermark_text=watermark_author,
        video_files=[_wrap_upload(d) for d in video_files_data] if video_files_data else None,
        bgm_file=_wrap_upload(bgm_file_data),
    )
    state = _wait_sub_task(vid, video_tasks.get_task_status, _STAGE_TIMEOUT["video"])
    _task_manager.update(task_id, stage="done", stage_label="完成", video_url=state.get("video_url"))
