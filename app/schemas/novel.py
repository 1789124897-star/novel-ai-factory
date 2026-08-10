"""小说 schemas"""

from typing import Optional

from pydantic import BaseModel


class CompileRequest(BaseModel):
    theme: str


class GenerateRequest(BaseModel):
    theme: str
    kernel: str
    target_words: int = 8000
    custom_prompt: Optional[str] = None
