from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

from app.schemas.metric import MetricRecord


# Keep this small and opinionated: these are the minimum signals used by simulation tuning.
DEFAULT_QUERIES: dict[str, str] = {
    "cpu.utilization": "avg by (service) (rate(process_cpu_seconds_total[5m]))",
    "memory.utilization": "avg by (service) (process_resident_memory_bytes)",
    "queue.depth": "avg by (service) (otelcol_exporter_queue_size)",
}


class PrometheusProvider:
    """Fetch instant Prometheus vectors and normalize them into MetricRecord entries."""

    def __init__(self, api_url: str, timeout_seconds: float = 6.0) -> None:
        self._api_url = api_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def fetch_metrics(self) -> list[MetricRecord]:
        now_ns = time.time_ns()
        output: list[MetricRecord] = []
        for metric_name, query in DEFAULT_QUERIES.items():
            # Query each metric independently to isolate failures and keep partial results useful.
            vector = self._query_instant(query)
            for sample in vector:
                metric_labels = sample.get("metric", {})
                value_pair = sample.get("value", [None, "0"]) 
                value = float(value_pair[1]) if len(value_pair) > 1 else 0.0

                # Use the sample timestamp when provided by Prometheus (seconds),
                # fall back to current time in nanoseconds otherwise. This keeps
                # rolling-window logic in sync with provider timestamps so small
                # windows (e.g. 30s) don't accidentally drop recent samples.
                ts_sec = value_pair[0]
                try:
                    ts_ns = int(float(ts_sec) * 1_000_000_000) if ts_sec is not None else now_ns
                except Exception:
                    ts_ns = now_ns

                # Normalize common label variations used across exporters.
                service_name = (
                    metric_labels.get("service")
                    or metric_labels.get("service_name")
                    or metric_labels.get("job")
                    or metric_labels.get("instance")
                    or "unknown"
                )

                attributes = {k: str(v) for k, v in metric_labels.items()}
                output.append(
                    MetricRecord(
                        service_name=str(service_name),
                        deployment_environment=attributes.get("deployment_environment"),
                        metric_name=metric_name,
                        metric_type="gauge",
                        value=value,
                        timestamp_unix_nano=ts_ns,
                        attributes=attributes,
                    )
                )
        return output

    def _query_instant(self, query: str) -> list[dict]:
        # Use instant queries because sync snapshots represent current operating conditions.
        params = urllib.parse.urlencode({"query": query})
        url = f"{self._api_url}/query?{params}"
        payload = _get_json(url, timeout_seconds=self._timeout_seconds)
        data = payload.get("data", {})
        result = data.get("result", []) if isinstance(data, dict) else []
        return result if isinstance(result, list) else []



def _get_json(url: str, timeout_seconds: float) -> dict:
    req = urllib.request.Request(url=url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
        body = response.read().decode("utf-8")
    decoded = json.loads(body)
    if not isinstance(decoded, dict):
        raise ValueError("Unexpected Prometheus response shape")
    return decoded
