from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class NormalizedLogRecord(BaseModel):
    time_unix_nano: int
    severity_text: Literal["TRACE", "DEBUG", "INFO", "WARN", "ERROR", "FATAL"] = "INFO"
    body: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = None
    span_id: str | None = None


class ScopeLogs(BaseModel):
    scope: str | None = None
    records: list[NormalizedLogRecord] = Field(default_factory=list)


class ResourceInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    service_name: str = Field(alias="service.name")
    deployment_environment: str | None = Field(default=None, alias="deployment.environment")


class ResourceLogs(BaseModel):
    resource: ResourceInfo
    scope_logs: list[ScopeLogs] = Field(default_factory=list)


class OTelLogBatch(BaseModel):
    resource_logs: list[ResourceLogs] = Field(default_factory=list)


class LogRecord(BaseModel):
    service_name: str
    deployment_environment: str | None = None
    timestamp_unix_nano: int
    severity_text: Literal["TRACE", "DEBUG", "INFO", "WARN", "ERROR", "FATAL"]
    body: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = None
    span_id: str | None = None
