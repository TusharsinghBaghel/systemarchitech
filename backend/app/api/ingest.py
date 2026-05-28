from fastapi import APIRouter

from app.activity.tracker import build_edge_activity_counts
from app.ingestion.log_normalize import normalize_log_batch
from app.ingestion.log_validate import validate_log_batch
from app.ingestion.metric_normalize import normalize_metric_batch
from app.ingestion.metric_validate import validate_metric_batch
from app.ingestion.normalize import normalize_span_batch
from app.ingestion.validate import validate_span_batch
from app.schemas.log import OTelLogBatch
from app.schemas.metric import OTelMetricBatch
from backend.app.schemas.span import OTelSpanBatch
from app.storage.memory_store import store

router = APIRouter(prefix="/ingest", tags=["ingest"])

# These endpoints accept OTLP-like payloads for spans, logs, and metrics. 
# They perform basic validation and normalization before storing the raw records
# in memory. For spans, they also update short-term edge activity counts used by the UI 
# to display current hotspots in the system. Each endpoint returns immediate stats about 
# the ingest operation, such as how many records were ingested and how many unique services 
# were touched, to help callers confirm that their telemetry is being received correctly.

@router.post("/spans")
def ingest_spans(batch: OTelSpanBatch) -> dict:
    # Guardrail checks for required fields and timestamp integrity.
    validate_span_batch(batch)
    # Convert OTLP-like nested payload into flat SpanRecord objects.
    spans = normalize_span_batch(batch)

    # Persist raw spans and update short-window edge activity counters used by the UI.
    store.add_spans(spans)
    store.add_edge_activity_counts(build_edge_activity_counts(spans, bucket_seconds=1))

    # Return immediate ingest stats so callers can confirm intake volume.
    return {
        "ingested_spans": len(spans),
        "trace_count": len({s.trace_id for s in spans}),
        "total_spans_stored": len(store.raw_spans),
    }


@router.post("/logs")
def ingest_logs(batch: OTelLogBatch) -> dict:
    validate_log_batch(batch)
    logs = normalize_log_batch(batch)
    store.add_logs(logs)
    return {
        "ingested_logs": len(logs),
        "services_touched": len({entry.service_name for entry in logs}),
        "total_logs_stored": len(store.raw_logs),
    }


@router.post("/metrics")
def ingest_metrics(batch: OTelMetricBatch) -> dict:
    validate_metric_batch(batch)
    metrics = normalize_metric_batch(batch)
    store.add_metrics(metrics)
    return {
        "ingested_metrics": len(metrics),
        "services_touched": len({entry.service_name for entry in metrics}),
        "total_metrics_stored": len(store.raw_metrics),
    }
