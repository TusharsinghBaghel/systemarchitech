from __future__ import annotations

import math
from statistics import mean, median

from app.schemas.model import DistributionSummary
from app.schemas.otel import SpanRecord


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    idx = min(len(sorted_values) - 1, math.ceil((p / 100.0) * len(sorted_values)) - 1)
    return float(sorted_values[max(0, idx)])


def distribution(values: list[float]) -> DistributionSummary:
    if not values:
        return DistributionSummary(mean=0.0, median=0.0, p95=0.0, p99=0.0, stddev=0.0)
    m = mean(values)
    variance = sum((v - m) ** 2 for v in values) / len(values)
    return DistributionSummary(
        mean=float(m),
        median=float(median(values)),
        p95=percentile(values, 95),
        p99=percentile(values, 99),
        stddev=float(math.sqrt(variance)),
    )


def error_rate(spans: list[SpanRecord]) -> float:
    if not spans:
        return 0.0
    errors = sum(1 for span in spans if span.status_code == "ERROR")
    return errors / len(spans)


def throughput_rps(spans: list[SpanRecord]) -> float:
    if not spans:
        return 0.0
    start = min(span.start_time for span in spans)
    end = max(span.end_time for span in spans)
    duration_sec = max((end - start) / 1_000_000_000, 1.0)
    return len(spans) / duration_sec
