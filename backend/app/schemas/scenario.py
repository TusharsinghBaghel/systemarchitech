from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ServiceOverride(BaseModel):
    latency_multiplier: float | None = None
    error_rate_override: float | None = None
    concurrency_limit_override: int | None = None


class EdgeOverride(BaseModel):
    latency_multiplier: float | None = None
    call_probability_override: float | None = None
    error_rate_override: float | None = None


class ScenarioRequest(BaseModel):
    traffic_multiplier: float = 1.0
    service_overrides: dict[str, ServiceOverride] = Field(default_factory=dict)
    edge_overrides: dict[str, EdgeOverride] = Field(default_factory=dict)
    duration_seconds: int = 60
    seed: int | None = None
    telemetry_influence_strength: Literal["none", "low", "medium", "high"] = "medium"
