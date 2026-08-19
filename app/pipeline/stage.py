"""管线阶段枚举 — 所有工作流的构建块。"""

from __future__ import annotations

from enum import Enum


class Stage(Enum):
    """各管线阶段。可按任意顺序组合运行。"""

    COMPILE = "compile"  # 编译叙事内核
    GENERATE = "generate"  # 四阶段小说生成（起承转合）

    @classmethod
    def full_pipeline(cls) -> list[Stage]:
        """返回默认全流程阶段顺序。"""
        return list(cls)
