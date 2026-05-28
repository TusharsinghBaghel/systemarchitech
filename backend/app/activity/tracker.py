from __future__ import annotations

import time
from collections import defaultdict

from app.model_builder.graph_builder import classify_call_type
from app.model_builder.trace_parser import group_spans_by_trace, map_span_by_id
from backend.app.schemas.span import SpanRecord

# Returns a Count dictionaary keyed by (caller_service, callee_service, call_type, bucket_start_ns) with integer counts of calls in that bucket.
# That is the no of calls from caller_service to callee_service of type call_type that started in the time bucket starting at bucket_start_ns.
def build_edge_activity_counts(
    spans: list[SpanRecord],
    bucket_seconds: int = 1,
) -> dict[tuple[str, str, str, int], int]:
    """Build per-edge activity counts grouped into fixed-size time buckets."""
    if bucket_seconds < 1:
        raise ValueError("bucket_seconds must be >= 1")

    bucket_ns = bucket_seconds * 1_000_000_000
    counts: dict[tuple[str, str, str, int], int] = defaultdict(int)

    traces = group_spans_by_trace(spans)
    now_ns = time.time_ns()
    bucket_start_ns = (now_ns // bucket_ns) * bucket_ns

    for trace_spans in traces.values():
        span_index = map_span_by_id(trace_spans)
        for span in trace_spans:
            if not span.parent_span_id:
                continue
            parent = span_index.get(span.parent_span_id)
            if not parent:
                continue
            if parent.service_name == span.service_name:
                continue

            call_type = classify_call_type(span)
            key = (parent.service_name, span.service_name, call_type, bucket_start_ns)
            counts[key] += 1

    return dict(counts)
