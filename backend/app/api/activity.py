from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas.activity import EdgeActivityResponse
from app.storage.memory_store import store

router = APIRouter(prefix="/activity", tags=["activity"])

#returns the most active edges in the last N seconds, where activity is defined as the number of spans/logs/metrics observed for that edge. Used for live updating UI panels showing current hotspots in the system.
@router.get("/edges", response_model=EdgeActivityResponse)
def get_edge_activity(
    window_seconds: int = Query(default=1, ge=1, le=30), #time window (starting from now and looking back)
    top_n: int = Query(default=12, ge=1, le=200),
) -> EdgeActivityResponse:
    return store.get_edge_activity(window_seconds=window_seconds, top_n=top_n)
