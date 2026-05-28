from __future__ import annotations

from collections import defaultdict

from app.schemas.log import LogRecord
from app.schemas.metric import MetricRecord
from app.schemas.model import LearnedModel
#takes an already built trace-based model and enriches each service with log 
# and metric signals, then converts those signals into simulation bias values.



def enrich_model_with_signals(
    model: LearnedModel,
    logs: list[LogRecord],
    metrics: list[MetricRecord],
) -> LearnedModel:
    # Nothing to enrich if the base model has no discovered services.
    if not model.services:
        return model

    # total logs per service and total error logs per service
    log_totals: dict[str, int] = defaultdict(int) 
    log_errors: dict[str, int] = defaultdict(int)
    # track the min and max timestamps of logs per service to estimate recent log intensity
    min_ts_by_service: dict[str, int] = {}
    max_ts_by_service: dict[str, int] = {}

    for entry in logs:
        svc = entry.service_name
        log_totals[svc] += 1
        if entry.severity_text in {"ERROR", "FATAL"}:
            log_errors[svc] += 1
        min_ts_by_service[svc] = min(min_ts_by_service.get(svc, entry.timestamp_unix_nano), entry.timestamp_unix_nano)
        max_ts_by_service[svc] = max(max_ts_by_service.get(svc, entry.timestamp_unix_nano), entry.timestamp_unix_nano)

    # Aggregate metric samples so per-service averages can be computed.
    metric_acc: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    metric_count: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for metric in metrics:
        svc = metric.service_name
        metric_acc[svc][metric.metric_name] += metric.value
        metric_count[svc][metric.metric_name] += 1

    # Work on a deep copy to keep the original learned model immutable.
    enriched = model.model_copy(deep=True)
    for service in enriched.services:
        svc = service.service_name

        total_logs = log_totals.get(svc, 0)
        error_logs = log_errors.get(svc, 0)
        # Log-derived error signal for the service.
        service.log_error_rate = (error_logs / total_logs) if total_logs > 0 else 0.0

        min_ts = min_ts_by_service.get(svc)
        max_ts = max_ts_by_service.get(svc)
        if min_ts is None or max_ts is None or max_ts <= min_ts:
            service.recent_log_events_per_sec = 0.0
        else:
            # Estimate log event intensity from observed log window.
            window_seconds = max(1e-6, (max_ts - min_ts) / 1_000_000_000)
            service.recent_log_events_per_sec = total_logs / window_seconds

        # Pull the canonical live metrics used by simulation biasing.
        avg_cpu = _avg_metric(metric_acc, metric_count, svc, "cpu.utilization")
        avg_mem = _avg_metric(metric_acc, metric_count, svc, "memory.utilization")
        avg_queue = _avg_metric(metric_acc, metric_count, svc, "queue.depth")

        service.live_cpu_utilization = avg_cpu
        service.live_memory_utilization = avg_mem
        service.live_queue_depth = avg_queue

        # Build bounded biases from multi-signal pressure indicators.
        #traces give historical behavior, hence we store bias using metrics and logs to capture current conditions that may not be reflected in the trace data.
        # These are intentionally conservative so traces remain primary.
        #these bias values are then used in the simulation to adjust the latency and error rates of the services, allowing the simulation to reflect current conditions more accurately.
        latency_bias = 0.0
        error_bias = 0.0
        if avg_cpu is not None:
            latency_bias += max(0.0, avg_cpu - 0.7)
        if avg_mem is not None:
            latency_bias += max(0.0, avg_mem - 0.75) * 0.8
        if avg_queue is not None:
            latency_bias += min(0.5, avg_queue / 200.0)

        if service.log_error_rate is not None:
            error_bias += min(0.3, service.log_error_rate * 0.6)
        if avg_queue is not None:
            error_bias += min(0.2, avg_queue / 300.0)

        # Clamp to [0, 1] so downstream simulation math is stable.
        service.simulation_latency_bias = min(1.0, latency_bias)
        service.simulation_error_bias = min(1.0, error_bias)

    return enriched


def _avg_metric(
    metric_acc: dict[str, dict[str, float]],
    metric_count: dict[str, dict[str, int]],
    service_name: str,
    metric_name: str,
) -> float | None:
    # Return None when no samples exist so callers can distinguish
    # "missing metric" from a true numeric zero.
    count = metric_count[service_name].get(metric_name, 0)
    if count <= 0:
        return None
    return metric_acc[service_name][metric_name] / count
