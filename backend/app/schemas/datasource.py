from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator
from urllib.parse import urlparse


TelemetrySourceKind = Literal["prometheus", "loki", "jaeger"]


class TelemetryDatasource(BaseModel):
    kind: TelemetrySourceKind
    url: str = Field(min_length=1)
    label: str | None = None
    enabled: bool = True

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parsed = urlparse(value.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Datasource URL must be an absolute http or https URL")
        return value.rstrip("/")


class TelemetryDatasourceRequest(BaseModel):
    datasources: list[TelemetryDatasource] = Field(default_factory=list)


class TelemetryDatasourceResponse(BaseModel):
    datasources: list[TelemetryDatasource] = Field(default_factory=list)
    source_mode: Literal["none", "direct", "external"] = "external"
    uses_defaults: bool = True
