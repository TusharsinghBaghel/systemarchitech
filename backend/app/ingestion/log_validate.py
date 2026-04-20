from __future__ import annotations

from fastapi import HTTPException

from app.schemas.log import OTelLogBatch


def validate_log_batch(batch: OTelLogBatch) -> None:
    if not batch.resource_logs:
        raise HTTPException(status_code=400, detail="resource_logs cannot be empty")
