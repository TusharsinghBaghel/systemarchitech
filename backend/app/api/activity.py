from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas.activity import EdgeActivityResponse
from app.storage.memory_store import store

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("/edges", response_model=EdgeActivityResponse)
def get_edge_activity(
    window_seconds: int = Query(default=1, ge=1, le=30),
    top_n: int = Query(default=12, ge=1, le=200),
) -> EdgeActivityResponse:
    return store.get_edge_activity(window_seconds=window_seconds, top_n=top_n)
