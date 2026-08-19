"""小说 schemas"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class CompileRequest(BaseModel):
    """编译叙事内核请求。"""

    theme: str = Field(min_length=1, max_length=200)


class GenerateRequest(BaseModel):
    """四阶段小说生成请求。"""

    theme: str = Field(min_length=1, max_length=200)
    kernel: str = Field(min_length=1)
    target_words: int = Field(default=8000, ge=100, le=50000)
    custom_prompt: Optional[str] = Field(default=None, max_length=2000)
