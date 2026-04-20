from __future__ import annotations

import json
import urllib.parse
import urllib.request
from collections import defaultdict

from app.schemas.otel import SpanRecord


class JaegerProvider:
    """Fetch traces from Jaeger and normalize them into SpanRecord objects."""

    def __init__(self, api_url: str, timeout_seconds: float = 6.0) -> None:
        self._api_url = api_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def fetch_spans(self, lookback_seconds: int = 300, limit: int = 200) -> list[SpanRecord]:
        # Use Jaeger search API to fetch a recent bounded window of traces.
        params = {
            "limit": str(max(1, limit)),
            "lookback": f"{max(1, lookback_seconds)}s",
        }
        url = f"{self._api_url}/traces?{urllib.parse.urlencode(params)}"
        payload = _get_json(url, timeout_seconds=self._timeout_seconds)
        traces = payload.get("data", [])
        spans: list[SpanRecord] = []

        for trace in traces:
            processes = trace.get("processes", {})
            for span in trace.get("spans", []):
                trace_id = str(span.get("traceID") or trace.get("traceID") or "")
                span_id = str(span.get("spanID") or "")
                if not trace_id or not span_id:
                    continue

                process_id = span.get("processID")
                process = processes.get(process_id, {}) if isinstance(processes, dict) else {}
                service_name = str(process.get("serviceName") or "unknown")

                # Merge process tags and span tags so downstream builders have one attribute map.
                tags = _tags_to_dict(span.get("tags", []))
                process_tags = _tags_to_dict(process.get("tags", []))
                attributes = {**process_tags, **tags}

                start_us = int(span.get("startTime") or 0)
                duration_us = int(span.get("duration") or 0)
                start_ns = start_us * 1000
                end_ns = start_ns + (duration_us * 1000)

                kind = str(tags.get("span.kind", "internal")).upper()
                mapped_kind = {
                    "SERVER": "SERVER",
                    "CLIENT": "CLIENT",
                    "PRODUCER": "PRODUCER",
                    "CONSUMER": "CONSUMER",
                }.get(kind, "INTERNAL")

                # Preserve CHILD_OF relationship to rebuild service edges later.
                parent_span_id = None
                for ref in span.get("references", []):
                    if str(ref.get("refType", "")).upper() == "CHILD_OF":
                        parent_span_id = str(ref.get("spanID") or "") or None
                        break

                status_code = "ERROR" if _is_error(tags) else "OK"

                spans.append(
                    SpanRecord(
                        trace_id=trace_id,
                        span_id=span_id,
                        parent_span_id=parent_span_id,
                        service_name=service_name,
                        span_name=str(span.get("operationName") or "unknown"),
                        kind=mapped_kind,
                        start_time=start_ns,
                        end_time=max(start_ns, end_ns),
                        duration_ms=max(0.0, duration_us / 1000.0),
                        attributes=attributes,
                        status_code=status_code,
                    )
                )

        # Keep only the latest span per ID if duplicates occur across traces/search results.
        dedup: dict[tuple[str, str], SpanRecord] = {}
        for span in spans:
            dedup[(span.trace_id, span.span_id)] = span

        return list(dedup.values())



def _get_json(url: str, timeout_seconds: float) -> dict:
    # Providers use the stdlib client to keep dependencies minimal for backend deployment.
    req = urllib.request.Request(url=url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
        body = response.read().decode("utf-8")
    decoded = json.loads(body)
    if not isinstance(decoded, dict):
        raise ValueError("Unexpected Jaeger response shape")
    return decoded



def _tags_to_dict(tags: list[dict]) -> dict[str, object]:
    # Jaeger tags are list-based; flatten to a dict keyed by tag name.
    out: dict[str, object] = {}
    for tag in tags or []:
        key = str(tag.get("key") or "")
        if not key:
            continue
        out[key] = tag.get("value")
    return out



def _is_error(tags: dict[str, object]) -> bool:
    # Accept both legacy 'error' tag and OTel status conventions.
    if tags.get("error") in {True, "true", "True", 1, "1"}:
        return True
    if str(tags.get("otel.status_code", "")).upper() == "ERROR":
        return True
    return False
