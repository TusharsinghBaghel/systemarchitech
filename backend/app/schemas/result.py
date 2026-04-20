from __future__ import annotations

from pydantic import BaseModel, Field


class MetricsSummary(BaseModel):
    avg_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    failure_rate: float
    completed_requests: int


class TimeSlice(BaseModel):
    second: int
    queue_depth_by_service: dict[str, int] = Field(default_factory=dict)


class SimulationResult(BaseModel):
    run_id: str
    baseline_summary: MetricsSummary
    simulated_summary: MetricsSummary
    bottlenecks: list[str] = Field(default_factory=list)
    per_service_metrics: dict = Field(default_factory=dict)
    per_edge_metrics: dict = Field(default_factory=dict)
    timeline: list[TimeSlice] = Field(default_factory=list)
