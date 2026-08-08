"""日志配置 — 在 ``main()`` 中调用一次即可。"""

import logging
import sys
from pathlib import Path

from .config import Settings


def setup_logging(settings: Settings) -> None:
    """配置根 logger，添加控制台和文件 handler。

    清除已有 handler 避免重复（如测试重新初始化时）。
    """
    root = logging.getLogger()
    root.handlers.clear()

    root.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
    formatter = logging.Formatter(settings.LOG_FORMAT)

    # 控制台
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    # 文件
    log_file = Path(settings.LOG_FILE)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # 抑制第三方日志噪音
    logging.getLogger("urllib3").setLevel(logging.WARNING)
