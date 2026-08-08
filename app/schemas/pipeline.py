"""管线 schemas"""

from pydantic import BaseModel


class RunRequest(BaseModel):
    theme: str
    target_words: int = 8000
