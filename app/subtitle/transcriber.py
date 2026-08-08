"""TurboScribe.ai 浏览器自动化音频转录。"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

from DrissionPage import ChromiumOptions, ChromiumPage

if TYPE_CHECKING:
    from ..core.config import Settings
    from ..core.paths import PathConfig

logger = logging.getLogger(__name__)


class TurboScribeTranscriber:
    """通过浏览器自动化 TurboScribe.ai 文件上传与转录。"""

    def __init__(self, settings: "Settings", paths: "PathConfig"):
        self._settings = settings
        self._paths = paths
        self._page: ChromiumPage | None = None

    # ── 上下文管理器 ────────────────────────────────────

    def __enter__(self) -> "TurboScribeTranscriber":
        self._start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # ── 浏览器生命周期 ──────────────────────────────────

    def _start(self) -> None:
        logger.info("正在启动浏览器 …")
        co = ChromiumOptions().set_browser_path(str(self._settings.BROWSER_PATH))
        if self._settings.HEADLESS:
            co.set_headless()

        self._page = ChromiumPage(co)
        self._page.get(self._settings.TARGET_URL)
        self._page.wait.load_start()
        logger.info("TurboScribe 页面已加载")

    def close(self) -> None:
        if self._page:
            self._page.quit()
            logger.info("浏览器已关闭")

    # ── 上传 ────────────────────────────────────────────

    def _click_trigger(self) -> bool:
        for label in ("转录文件", "转录您的第一个文件"):
            for el in self._page.eles(
                f'xpath://span[contains(text(),"{label}")]'
            ):
                try:
                    el.click()
                    logger.info("已点击 '%s'", label)
                    return True
                except Exception:
                    continue
        logger.error("上传触发按钮未找到")
        return False

    def upload_file(self, file_path: Path) -> None:
        if not file_path.exists():
            raise FileNotFoundError(f"文件未找到: {file_path}")

        logger.info("正在上传: %s", file_path)
        self._click_trigger()

        file_input = self._page.ele(
            "xpath://input[@type='file' and contains(@accept, 'audio')]",
            timeout=15,
        )
        if not file_input:
            raise RuntimeError("文件输入元素未找到")

        file_input.input(str(file_path))
        time.sleep(6)  # 等待 TurboScribe 处理文件
        logger.info("上传完成")

    # ── 转录 ────────────────────────────────────────────

    def start_transcription(self) -> None:
        logger.info("正在开始转录 …")
        btn = self._page.ele('xpath://span[text()="转录"]')
        if not btn:
            raise RuntimeError("转录按钮未找到")
        btn.click()

    def wait_for_completion(self) -> None:
        logger.info("等待转录完成 …")
        deadline = time.time() + self._settings.TIMEOUT
        while time.time() < deadline:
            try:
                row = self._page.ele('xpath://span[text()="打开转录文件"]')
                if row:
                    row.click()
                    logger.info("转录完成")
                    return
            except Exception:
                pass
            time.sleep(self._settings.POLL_INTERVAL)
        raise TimeoutError(
            f"转录超时 ({self._settings.TIMEOUT}s)"
        )

    # ── 抓取 ────────────────────────────────────────────

    def _scrape_text(self) -> Path:
        logger.info("正在抓取转录文本 …")
        groups = self._page.eles(
            'xpath://div[contains(@class,"space-y-4")]//span[.//span[@data-start]]'
        )
        lines = []
        for group in groups:
            time_el = group.ele("xpath:.//span[@data-timestamp]")
            content_el = group.ele("xpath:.//span[@data-start]")
            if not time_el or not content_el:
                continue
            lines.append(f"{time_el.text.strip()} {content_el.text.strip()}")

        out = self._paths.crawler_unprocessed_srt
        out.write_text("\n".join(lines), encoding="utf-8")
        logger.info("转录文本已保存 → %s", out)
        return out

    # ── 全流程 ──────────────────────────────────────────

    def transcribe(self, file_path: Path) -> Path:
        """运行完整转录流程并返回原始输出路径。"""
        self.upload_file(file_path)
        self.start_transcription()
        self.wait_for_completion()
        return self._scrape_text()
