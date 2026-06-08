from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    # API server bind settings.
    api_host: str = "127.0.0.1"
    api_port: int = 8010
    # External observability endpoints consumed by provider adapters.
    jaeger_api_url: str = "http://127.0.0.1:18080/jaeger/api"
    prometheus_api_url: str = "http://127.0.0.1:18080/prometheus/api/v1"
    loki_api_url: str = "http://127.0.0.1:18080/loki"
    # Polling/query bounds to prevent expensive full-range scans.
    external_sync_window_seconds: int = 3
    external_sync_limit: int = 200
    external_timeout_seconds: float = 6.0



def load_settings() -> Settings:
    # Keep settings parsing centralized so adapters stay configuration-agnostic.
    return Settings(
        api_host=os.getenv("API_HOST", "127.0.0.1"),
        api_port=max(1, int(os.getenv("API_PORT", "8010"))),
        jaeger_api_url=os.getenv("JAEGER_API_URL", "http://127.0.0.1:18080/jaeger/api").rstrip("/"),
        prometheus_api_url=os.getenv("PROMETHEUS_API_URL", "http://127.0.0.1:18080/prometheus/api/v1").rstrip("/"),
        loki_api_url=os.getenv("LOKI_API_URL", "http://127.0.0.1:18080/loki").rstrip("/"),
        external_sync_window_seconds=max(3, int(os.getenv("EXTERNAL_SYNC_WINDOW_SECONDS", "3"))),
        external_sync_limit=max(1, int(os.getenv("EXTERNAL_SYNC_LIMIT", "200"))),
        external_timeout_seconds=max(1.0, float(os.getenv("EXTERNAL_TIMEOUT_SECONDS", "6"))),
    )


settings = load_settings()
