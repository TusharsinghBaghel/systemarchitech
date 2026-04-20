from __future__ import annotations

from app.schemas.log import LogRecord, OTelLogBatch


def normalize_log_batch(batch: OTelLogBatch) -> list[LogRecord]:
    normalized: list[LogRecord] = []
    for resource_log in batch.resource_logs:
        service_name = resource_log.resource.service_name
        environment = resource_log.resource.deployment_environment
        for scope_logs in resource_log.scope_logs:
            for record in scope_logs.records:
                normalized.append(
                    LogRecord(
                        service_name=service_name,
                        deployment_environment=environment,
                        timestamp_unix_nano=record.time_unix_nano,
                        severity_text=record.severity_text,
                        body=record.body,
                        attributes=record.attributes,
                        trace_id=record.trace_id,
                        span_id=record.span_id,
                    )
                )
    return normalized
