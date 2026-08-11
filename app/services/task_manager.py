"""轻量异步任务管理。"""

import logging
import threading
import uuid
from collections.abc import Callable
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TaskManager:
    """后台任务创建、状态查询、生命周期管理。"""

    def __init__(self) -> None:
        self._tasks: dict[str, dict] = {}
        self._lock = threading.Lock()

    def start(self, target: Callable[..., None], *args: Any) -> str:
        task_id = str(uuid.uuid4())[:8]
        state: dict[str, Any] = {"status": "running", "error": None}
        with self._lock:
            self._tasks[task_id] = state

        def _run() -> None:
            try:
                target(task_id, *args)
                self.update(task_id, status="done")
            except Exception as e:
                logger.exception("任务失败 task_id=%s", task_id)
                self.update(task_id, status="error", error=str(e))

        threading.Thread(target=_run, daemon=True).start()
        return task_id

    def get(self, task_id: str) -> Optional[dict]:
        with self._lock:
            task = self._tasks.get(task_id)
            return dict(task) if task else None

    def update(self, task_id: str, **kwargs: Any) -> None:
        """线程安全地更新任务字段。"""
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                task.update(kwargs)
