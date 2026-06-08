from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.datasource import TelemetryDatasourceRequest, TelemetryDatasourceResponse
from app.services.telemetry_sync import telemetry_sync_service
from app.storage.memory_store import store

router = APIRouter(prefix="/telemetry", tags=["telemetry"])
# This API provides endpoints to query recent telemetry data and trigger manual syncs.

@router.get("/logs")
def recent_logs(limit: int = 100, service_name: str | None = None) -> dict:
    # Read path for UI panels: returns newest-first logs with optional service filter.
    entries = store.get_recent_logs(limit=limit, service_name=service_name)
    return {
        "count": len(entries),
        "logs": [entry.model_dump() for entry in entries],
    }


@router.get("/metrics/live")
def live_metrics(window_seconds: int = 30) -> dict:
    # Returns windowed averages by service/metric for lightweight dashboard cards.
    snapshot = store.get_live_metric_snapshot(window_seconds=window_seconds)
    return {
        "window_seconds": window_seconds,
        "services": snapshot,
    }


@router.post("/sync")
def sync_external_telemetry() -> dict:
    # Manual trigger used by UI or ops scripts to force an immediate refresh.
    return telemetry_sync_service.sync_once()


@router.get("/status")
def telemetry_status() -> dict:
    # Provider health and snapshot metadata for observability/debugging.
    return store.get_telemetry_status()


@router.get("/datasources", response_model=TelemetryDatasourceResponse)
def get_datasources() -> TelemetryDatasourceResponse:
    datasources = telemetry_sync_service.get_effective_datasources()
    return TelemetryDatasourceResponse(
        datasources=datasources,
        source_mode=store.telemetry_source_mode,
        uses_defaults=not bool(store.get_telemetry_datasources()),
    )


@router.put("/datasources")
def set_datasources(payload: TelemetryDatasourceRequest) -> dict:
    # Save user-selected datasource links, then immediately sync from them.
    if not payload.datasources:
        raise HTTPException(status_code=400, detail="Add at least one datasource before clicking Done")

    store.set_telemetry_datasources(payload.datasources)
    return telemetry_sync_service.sync_once()
