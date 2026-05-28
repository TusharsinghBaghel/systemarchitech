from __future__ import annotations

from fastapi import HTTPException

from backend.app.schemas.span import OTelSpanBatch


def validate_span_batch(batch: OTelSpanBatch) -> None:
    if not batch.resource_spans:
        raise HTTPException(status_code=400, detail="resource_spans cannot be empty")
