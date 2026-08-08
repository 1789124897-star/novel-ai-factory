"""小说 schemas"""

from pydantic import BaseModel


class CompileRequest(BaseModel):
    theme: str
