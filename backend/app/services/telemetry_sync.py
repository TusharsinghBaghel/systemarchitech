from __future__ import annotations

import time

from app.config import settings
from app.providers.jaeger import JaegerProvider
from app.providers.loki import LokiProvider
from app.providers.prometheus import PrometheusProvider
from app.storage.memory_store import store


class TelemetrySyncService:
    """Orchestrates multi-provider pulls and writes a unified in-memory snapshot."""

    def __init__(self) -> None:
        self._jaeger = JaegerProvider(settings.jaeger_api_url, timeout_seconds=settings.external_timeout_seconds)
        self._prom = PrometheusProvider(settings.prometheus_api_url, timeout_seconds=settings.external_timeout_seconds)
        self._loki = LokiProvider(settings.loki_api_url, timeout_seconds=settings.external_timeout_seconds)

    def sync_once(self) -> dict:
        # Fetch each signal independently so partial provider failures do not block sync.
        provider_status: dict[str, dict] = {}
        spans = []
        logs = []
        metrics = []

        spans, provider_status["jaeger"] = self._safe_fetch(
            provider_name="jaeger",
            fetcher=lambda: self._jaeger.fetch_spans(
                lookback_seconds=settings.external_sync_window_seconds,
                limit=settings.external_sync_limit,
            ),
        )

        metrics, provider_status["prometheus"] = self._safe_fetch(
            provider_name="prometheus",
            fetcher=self._prom.fetch_metrics,
        )

        logs, provider_status["loki"] = self._safe_fetch(
            provider_name="loki",
            fetcher=lambda: self._loki.fetch_logs(
                lookback_seconds=settings.external_sync_window_seconds,
                limit=settings.external_sync_limit,
            ),
        )

        store.replace_external_snapshot(spans=spans, logs=logs, metrics=metrics, provider_status=provider_status)

        return {
            "source_mode": "external",
            "synced": True,
            "spans": len(spans),
            "logs": len(logs),
            "metrics": len(metrics),
            "providers": provider_status,
            "synced_at": time.time(),
        }

    def status(self) -> dict:
        return store.get_external_sync_status()

    def _safe_fetch(self, provider_name: str, fetcher) -> tuple[list, dict]:
        # Capture errors per provider and return empty data instead of raising.
        try:
            items = fetcher()
            return items, {
                "name": provider_name,
                "ok": True,
                "count": len(items),
                "error": None,
            }
        except Exception as exc:
            return [], {
                "name": provider_name,
                "ok": False,
                "count": 0,
                "error": str(exc),
            }


telemetry_sync_service = TelemetrySyncService()
