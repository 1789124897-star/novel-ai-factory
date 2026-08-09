"""轻量异步任务管理 — 内存存储 + 后台线程，原型用。"""

import threading
import uuid
from collections.abc import Callable
from typing import Any, Optional

logger = __import__("logging").getLogger(__name__)


class TaskManager:
    """后台任务创建、状态查询、生命周期管理。
    """

    def __init__(self) -> None:

        self._tasks: dict[str, dict] = {}
        self._lock = threading.Lock()

    def start(self, target: Callable[..., None], *args: Any, **initial: Any) -> str:

        task_id = str(uuid.uuid4())[:8]
        state = {"status": "running", "error": None, **initial}
        with self._lock:
            self._tasks[task_id] = state

        thread = threading.Thread(target=self._wrap, args=(target, task_id, *args), daemon=True)
        thread.start()
        return task_id

    def get(self, task_id: str) -> Optional[dict]:
        return self._tasks.get(task_id)

    def update(self, task_id: str, **kwargs: Any) -> None:
        """线程安全地更新任务字段。"""
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                task.update(kwargs)

    def _wrap(self, target: Callable[..., None], task_id: str, *args: Any) -> None:
        try:
            target(task_id, *args)
            self.update(task_id, status="done")
        except Exception as e:
            logger.exception("任务失败 task_id=%s", task_id)
            self.update(task_id, status="error", error=str(e))
