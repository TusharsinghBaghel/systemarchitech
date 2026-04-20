from __future__ import annotations

from pydantic import BaseModel, Field


class EdgeActivityItem(BaseModel):
    source_service: str
    target_service: str
    call_type: str
    activity_count: int = Field(ge=0)
    activity_rps: float = Field(ge=0)


class EdgeActivityResponse(BaseModel):
    generated_at_unix_nano: int
    window_seconds: int = Field(ge=1)
    top_n: int = Field(ge=1)
    edges: list[EdgeActivityItem] = Field(default_factory=list)
