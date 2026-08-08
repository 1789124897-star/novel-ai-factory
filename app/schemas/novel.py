"""小说 schemas"""

from typing import Any

from pydantic import BaseModel


class CompileRequest(BaseModel):
    theme: str


class GenerateRequest(BaseModel):
    theme: str
    kernel: str  # 内核文本，Markdown 格式
