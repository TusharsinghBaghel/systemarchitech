from __future__ import annotations

from app.schemas.otel import OTelSpanBatch, SpanRecord


def normalize_span_batch(batch: OTelSpanBatch) -> list[SpanRecord]:
    normalized: list[SpanRecord] = []
    for resource_span in batch.resource_spans:
        service_name = resource_span.resource.service_name
        for scope_spans in resource_span.scope_spans:
            for span in scope_spans.spans:
                duration_ms = max(0.0, (span.end_time_unix_nano - span.start_time_unix_nano) / 1_000_000)
                normalized.append(
                    SpanRecord(
                        trace_id=span.trace_id,
                        span_id=span.span_id,
                        parent_span_id=span.parent_span_id,
                        service_name=service_name,
                        span_name=span.name,
                        kind=span.kind,
                        start_time=span.start_time_unix_nano,
                        end_time=span.end_time_unix_nano,
                        duration_ms=duration_ms,
                        attributes=span.attributes,
                        status_code=span.status_code,
                    )
                )
    return normalized
