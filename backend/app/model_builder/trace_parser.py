from __future__ import annotations

from collections import defaultdict

from app.schemas.span import SpanRecord


def group_spans_by_trace(spans: list[SpanRecord]) -> dict[str, list[SpanRecord]]:
    traces: dict[str, list[SpanRecord]] = defaultdict(list)
    for span in spans:
        traces[span.trace_id].append(span)
    for trace_id in traces:
        traces[trace_id].sort(key=lambda s: s.start_time)
    return dict(traces)


def map_span_by_id(trace_spans: list[SpanRecord]) -> dict[str, SpanRecord]:
    return {span.span_id: span for span in trace_spans}
