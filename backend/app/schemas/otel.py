from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class NormalizedSpan(BaseModel):
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    name: str
    kind: Literal["SERVER", "CLIENT", "INTERNAL", "PRODUCER", "CONSUMER"] = "INTERNAL"
    start_time_unix_nano: int
    end_time_unix_nano: int
    status_code: Literal["OK", "ERROR"] = "OK"
    attributes: dict[str, Any] = Field(default_factory=dict)


class ScopeSpans(BaseModel):
    scope: str | None = None
    spans: list[NormalizedSpan] = Field(default_factory=list)


class ResourceInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    service_name: str = Field(alias="service.name")
    deployment_environment: str | None = Field(default=None, alias="deployment.environment")


class ResourceSpans(BaseModel):
    resource: ResourceInfo
    scope_spans: list[ScopeSpans] = Field(default_factory=list)


class OTelSpanBatch(BaseModel):
    resource_spans: list[ResourceSpans] = Field(default_factory=list)


class SpanRecord(BaseModel):
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    service_name: str
    span_name: str
    kind: Literal["SERVER", "CLIENT", "INTERNAL", "PRODUCER", "CONSUMER"]
    start_time: int
    end_time: int
    duration_ms: float
    attributes: dict[str, Any] = Field(default_factory=dict)
    status_code: Literal["OK", "ERROR"]
