"""管线服务 — 封装运行器编排和内存任务存储。"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from typing import Optional

from app.pipeline.runner import PipelineRunner


@dataclass
class _TaskState:
    task_id: str
    status: str = "PENDING"
    progress: float = 0.0
    stage: str = ""
    theme: str = ""
    result: Optional[dict] = None
    error: str = ""


class PipelineService:
    """管线业务逻辑层"""

    def __init__(self) -> None:
        self._tasks: dict[str, _TaskState] = {}
        self._lock = threading.Lock()

    def start(self, theme: str, target_words: int = 8000) -> str:
        """后台线程启动管线运行。

        Returns:
            用于轮询的 ``task_id``。
        """
        task_id = uuid.uuid4().hex[:12]
        state = _TaskState(task_id=task_id, status="PENDING", theme=theme)

        with self._lock:
            self._tasks[task_id] = state

        def _run() -> None:
            state.status = "RUNNING"

            def on_progress(pct: float, stage: str) -> None:
                with self._lock:
                    state.progress = round(pct, 3)
                    state.stage = stage

            try:
                runner = PipelineRunner()
                result = runner.run(
                    theme,
                    target_words=target_words,
                    on_progress=on_progress,
                )
                with self._lock:
                    state.status = "SUCCESS"
                    state.progress = 1.0
                    state.result = result
            except Exception as e:
                with self._lock:
                    state.status = "FAILURE"
                    state.error = str(e)

        threading.Thread(target=_run, daemon=True).start()
        return task_id

    def get_status(self, task_id: str) -> _TaskState | None:
        with self._lock:
            return self._tasks.get(task_id)
