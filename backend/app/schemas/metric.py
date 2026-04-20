from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class NormalizedMetricRecord(BaseModel):
    metric_name: str
    metric_type: Literal["gauge", "counter", "histogram"] = "gauge"
    value: float
    time_unix_nano: int
    attributes: dict[str, Any] = Field(default_factory=dict)


class ScopeMetrics(BaseModel):
    scope: str | None = None
    records: list[NormalizedMetricRecord] = Field(default_factory=list)


class ResourceInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    service_name: str = Field(alias="service.name")
    deployment_environment: str | None = Field(default=None, alias="deployment.environment")


class ResourceMetrics(BaseModel):
    resource: ResourceInfo
    scope_metrics: list[ScopeMetrics] = Field(default_factory=list)


class OTelMetricBatch(BaseModel):
    resource_metrics: list[ResourceMetrics] = Field(default_factory=list)


class MetricRecord(BaseModel):
    service_name: str
    deployment_environment: str | None = None
    metric_name: str
    metric_type: Literal["gauge", "counter", "histogram"]
    value: float
    timestamp_unix_nano: int
    attributes: dict[str, Any] = Field(default_factory=dict)
