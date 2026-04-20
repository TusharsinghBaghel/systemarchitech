from __future__ import annotations

from app.model_builder.stats_builder import percentile


def summarize_latencies(values: list[float]) -> tuple[float, float, float]:
    if not values:
        return 0.0, 0.0, 0.0
    avg = sum(values) / len(values)
    p95 = percentile(values, 95)
    p99 = percentile(values, 99)
    return avg, p95, p99
