from __future__ import annotations

from pydantic import BaseModel, Field


class DistributionSummary(BaseModel):
    mean: float
    median: float
    p95: float
    p99: float
    stddev: float


class ServiceNodeModel(BaseModel):
    service_name: str
    instance_count: int = 1
    concurrency_limit: int = 4
    latency_distribution: DistributionSummary
    error_rate: float
    throughput_rps: float
    log_error_rate: float | None = None
    recent_log_events_per_sec: float | None = None
    live_cpu_utilization: float | None = None
    live_memory_utilization: float | None = None
    live_queue_depth: float | None = None
    simulation_latency_bias: float = 0.0
    simulation_error_bias: float = 0.0


class ServiceEdgeModel(BaseModel):
    source_service: str
    target_service: str
    call_type: str
    latency_distribution: DistributionSummary
    call_probability: float
    error_rate: float


class LearnedModel(BaseModel):
    services: list[ServiceNodeModel] = Field(default_factory=list)
    edges: list[ServiceEdgeModel] = Field(default_factory=list)
    trace_count: int = 0
    span_count: int = 0
