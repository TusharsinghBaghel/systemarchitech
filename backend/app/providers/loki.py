from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request

from app.schemas.log import LogRecord


class LokiProvider:
    """Fetch recent logs from Loki and map them to LogRecord entries."""

    def __init__(self, base_url: str, timeout_seconds: float = 6.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def fetch_logs(self, lookback_seconds: int = 300, limit: int = 200) -> list[LogRecord]:
        # Query a bounded range to avoid scanning the full log history.
        now_ns = time.time_ns()
        start_ns = now_ns - (max(1, lookback_seconds) * 1_000_000_000)
        params = {
            "query": '{service=~".+"}',
            "start": str(start_ns),
            "end": str(now_ns),
            "limit": str(max(1, limit)),
            "direction": "BACKWARD",
        }
        url = f"{self._base_url}/loki/api/v1/query_range?{urllib.parse.urlencode(params)}"
        payload = _get_json(url, timeout_seconds=self._timeout_seconds)
        data = payload.get("data", {})
        result = data.get("result", []) if isinstance(data, dict) else []

        logs: list[LogRecord] = []
        for stream in result if isinstance(result, list) else []:
            labels = stream.get("stream", {})
            values = stream.get("values", [])
            service_name = (
                labels.get("service")
                or labels.get("service_name")
                or labels.get("app")
                or "unknown"
            )

            for pair in values:
                if len(pair) < 2:
                    continue
                ts_ns = int(pair[0])
                body = str(pair[1])
                # Loki payloads are free-form; infer minimal severity for downstream scoring.
                severity = _infer_severity(body)
                logs.append(
                    LogRecord(
                        service_name=str(service_name),
                        deployment_environment=labels.get("deployment_environment"),
                        timestamp_unix_nano=ts_ns,
                        severity_text=severity,
                        body=body,
                        attributes={k: str(v) for k, v in labels.items()},
                        trace_id=_find_trace_id(body),
                        span_id=None,
                    )
                )

        logs.sort(key=lambda entry: entry.timestamp_unix_nano, reverse=True)
        return logs[: max(1, limit)]



def _get_json(url: str, timeout_seconds: float) -> dict:
    req = urllib.request.Request(url=url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
        body = response.read().decode("utf-8")
    decoded = json.loads(body)
    if not isinstance(decoded, dict):
        raise ValueError("Unexpected Loki response shape")
    return decoded



def _infer_severity(message: str) -> str:
    # Lightweight keyword heuristic to keep provider integration format-agnostic.
    upper = message.upper()
    if "FATAL" in upper:
        return "FATAL"
    if "ERROR" in upper or "EXCEPTION" in upper:
        return "ERROR"
    if "WARN" in upper:
        return "WARN"
    if "DEBUG" in upper:
        return "DEBUG"
    if "TRACE" in upper:
        return "TRACE"
    return "INFO"



def _find_trace_id(message: str) -> str | None:
    # Best-effort trace correlation when logs embed trace IDs in plain text.
    match = re.search(r"trace[_-]?id[=: ]+([a-fA-F0-9]{8,32})", message)
    if not match:
        return None
    return match.group(1)
