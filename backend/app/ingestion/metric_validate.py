from __future__ import annotations

from fastapi import HTTPException

from app.schemas.metric import OTelMetricBatch


def validate_metric_batch(batch: OTelMetricBatch) -> None:
    if not batch.resource_metrics:
        raise HTTPException(status_code=400, detail="resource_metrics cannot be empty")
