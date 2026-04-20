from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
import json
from pathlib import Path
import threading
import time

from app.schemas.log import LogRecord
from app.schemas.metric import MetricRecord
from app.schemas.model import LearnedModel
from app.schemas.otel import SpanRecord
from app.schemas.activity import EdgeActivityItem, EdgeActivityResponse
from app.schemas.result import SimulationResult


@dataclass
class MemoryStore:
    # Unified in-memory snapshot consumed by model building, telemetry APIs, and simulation.
    raw_spans: list[SpanRecord] = field(default_factory=list)
    raw_logs: list[LogRecord] = field(default_factory=list)
    raw_metrics: list[MetricRecord] = field(default_factory=list)
    learned_model: LearnedModel | None = None
    simulation_runs: dict[str, SimulationResult] = field(default_factory=dict)
    edge_activity_buckets: dict[tuple[str, str, str], deque[tuple[int, int]]] = field(
        default_factory=lambda: defaultdict(deque)
    )
    edge_activity_retention_seconds: int = 300
    run_history_path: Path = field(
        default_factory=lambda: Path(__file__).resolve().parents[2] / "data" / "simulation_runs.json"
    )
    external_sync_status: dict[str, object] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self) -> None:
        self._load_simulation_runs()

    def add_spans(self, spans: list[SpanRecord]) -> None:
        with self._lock:
            self.raw_spans.extend(spans)

    def add_logs(self, logs: list[LogRecord]) -> None:
        with self._lock:
            self.raw_logs.extend(logs)

    def add_metrics(self, metrics: list[MetricRecord]) -> None:
        with self._lock:
            self.raw_metrics.extend(metrics)

    def replace_external_snapshot(
        self,
        spans: list[SpanRecord],
        logs: list[LogRecord],
        metrics: list[MetricRecord],
        provider_status: dict[str, dict],
    ) -> None:
        # External sync is authoritative: replace lists instead of appending incremental deltas.
        with self._lock:
            self.raw_spans = list(spans)
            self.raw_logs = list(logs)
            self.raw_metrics = list(metrics)
            self.external_sync_status = {
                "last_synced_at": time.time(),
                "provider_status": provider_status,
                "counts": {
                    "spans": len(self.raw_spans),
                    "logs": len(self.raw_logs),
                    "metrics": len(self.raw_metrics),
                },
            }

    def get_external_sync_status(self) -> dict:
        # Exposes coarse health/freshness details without leaking provider-specific payloads.
        with self._lock:
            return {
                "source_mode": "external",
                "counts": {
                    "spans": len(self.raw_spans),
                    "logs": len(self.raw_logs),
                    "metrics": len(self.raw_metrics),
                },
                "sync": self.external_sync_status,
            }

    def get_recent_logs(self, limit: int = 100, service_name: str | None = None) -> list[LogRecord]:
        with self._lock:
            logs = self.raw_logs
            if service_name:
                logs = [entry for entry in logs if entry.service_name == service_name]
            # Newest-first ordering keeps UI rendering and polling logic simple.
            return list(reversed(logs[-max(1, min(limit, 500)) :]))

    def get_live_metric_snapshot(self, window_seconds: int = 30) -> dict[str, dict[str, float]]:
        # Build a rolling-window average for each metric per service.
        window_ns = max(1, window_seconds) * 1_000_000_000
        cutoff_ns = time.time_ns() - window_ns

        with self._lock:
            metrics = [m for m in self.raw_metrics if m.timestamp_unix_nano >= cutoff_ns]

        snapshot: dict[str, dict[str, float]] = defaultdict(dict)
        counts: dict[tuple[str, str], int] = defaultdict(int)

        for metric in metrics:
            key = (metric.service_name, metric.metric_name)
            counts[key] += 1
            prev = snapshot[metric.service_name].get(metric.metric_name, 0.0)
            snapshot[metric.service_name][metric.metric_name] = prev + metric.value

        for service_name, service_metrics in snapshot.items():
            for metric_name in list(service_metrics):
                divisor = counts[(service_name, metric_name)]
                if divisor > 0:
                    service_metrics[metric_name] = service_metrics[metric_name] / divisor

        return snapshot

    def add_edge_activity_counts(
        self,
        counts: dict[tuple[str, str, str, int], int],
    ) -> None:
        # Maintains compact per-edge activity buckets for recent traffic visualization.
        if not counts:
            return

        retention_ns = self.edge_activity_retention_seconds * 1_000_000_000
        now_ns = time.time_ns()

        with self._lock:
            for (source, target, call_type, bucket_start_ns), count in counts.items():
                edge_key = (source, target, call_type)
                bucket_queue = self.edge_activity_buckets[edge_key]
                if bucket_queue and bucket_queue[-1][0] == bucket_start_ns:
                    prev_bucket_start, prev_count = bucket_queue[-1]
                    bucket_queue[-1] = (prev_bucket_start, prev_count + count)
                else:
                    bucket_queue.append((bucket_start_ns, count))

            purge_cutoff = now_ns - retention_ns
            for edge_key, bucket_queue in list(self.edge_activity_buckets.items()):
                while bucket_queue and bucket_queue[0][0] < purge_cutoff:
                    bucket_queue.popleft()
                if not bucket_queue:
                    del self.edge_activity_buckets[edge_key]

    def get_edge_activity(self, window_seconds: int = 1, top_n: int = 12) -> EdgeActivityResponse:
        # Returns top-N active edges in the requested time window.
        window_ns = window_seconds * 1_000_000_000
        now_ns = time.time_ns()
        cutoff_ns = now_ns - window_ns

        with self._lock:
            snapshot = {
                edge_key: list(bucket_queue)
                for edge_key, bucket_queue in self.edge_activity_buckets.items()
            }

        items: list[EdgeActivityItem] = []
        for (source, target, call_type), bucket_entries in snapshot.items():
            activity_count = sum(count for bucket_start, count in bucket_entries if bucket_start >= cutoff_ns)
            if activity_count <= 0:
                continue
            items.append(
                EdgeActivityItem(
                    source_service=source,
                    target_service=target,
                    call_type=call_type,
                    activity_count=activity_count,
                    activity_rps=activity_count / max(window_seconds, 1),
                )
            )

        items.sort(key=lambda item: item.activity_count, reverse=True)

        return EdgeActivityResponse(
            generated_at_unix_nano=now_ns,
            window_seconds=window_seconds,
            top_n=top_n,
            edges=items[:top_n],
        )

    def clear_model(self) -> None:
        self.learned_model = None

    def add_simulation_run(self, result: SimulationResult) -> None:
        self.simulation_runs[result.run_id] = result
        self._save_simulation_runs()

    def _load_simulation_runs(self) -> None:
        if not self.run_history_path.exists():
            return
        try:
            payload = json.loads(self.run_history_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return
            for run_id, run_data in payload.items():
                self.simulation_runs[run_id] = SimulationResult.model_validate(run_data)
        except Exception:
            # Best-effort startup: skip loading invalid history instead of failing app boot.
            self.simulation_runs = {}

    def _save_simulation_runs(self) -> None:
        self.run_history_path.parent.mkdir(parents=True, exist_ok=True)
        serialized = {
            run_id: result.model_dump()
            for run_id, result in self.simulation_runs.items()
        }
        self.run_history_path.write_text(
            json.dumps(serialized, indent=2),
            encoding="utf-8",
        )


store = MemoryStore()
