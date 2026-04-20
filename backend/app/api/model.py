from fastapi import APIRouter, HTTPException

from app.model_builder.graph_builder import build_model
from app.model_builder.log_metric_builder import enrich_model_with_signals
from app.storage.memory_store import store

router = APIRouter(prefix="/model", tags=["model"])


@router.post("/build")
def build_current_model() -> dict:
    if not store.raw_spans:
        raise HTTPException(status_code=400, detail="No spans ingested")
    model = build_model(store.raw_spans)
    model = enrich_model_with_signals(model, store.raw_logs, store.raw_metrics)
    store.learned_model = model
    return {
        "service_count": len(model.services),
        "edge_count": len(model.edges),
        "trace_count": model.trace_count,
        "span_count": model.span_count,
        "log_count": len(store.raw_logs),
        "metric_count": len(store.raw_metrics),
    }


@router.get("")
def get_model() -> dict:
    if not store.learned_model:
        raise HTTPException(status_code=404, detail="Model not built")
    return store.learned_model.model_dump()
