"""小说服务 — 编译逻辑"""

from __future__ import annotations

from app.core.config import settings
from app.core.paths import PathConfig
from app.novel.compiler import ThemeCompiler


class NovelService:
    """小说业务逻辑层"""

    @staticmethod
    def compile_kernel(theme: str) -> dict:
        """编译主题为结构化叙事内核"""
        paths = PathConfig.from_settings(settings, theme=theme)
        compiler = ThemeCompiler(settings, paths)

        try:
            kernel = compiler.compile(theme)
            compiler.save_kernel(kernel, paths.kernel_file)
        finally:
            compiler.close()

        return {
            "theme": theme,
            "kernel": kernel,
            "kernel_path": str(paths.kernel_file),
        }
