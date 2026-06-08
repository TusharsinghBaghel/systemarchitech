from __future__ import annotations

import time

from app.config import settings
from app.schemas.datasource import TelemetryDatasource
from app.providers.jaeger import JaegerProvider
from app.providers.loki import LokiProvider
from app.providers.prometheus import PrometheusProvider
from app.storage.memory_store import store


class TelemetrySyncService:
    """Orchestrates multi-provider pulls and writes a unified in-memory snapshot."""

    def get_effective_datasources(self) -> list[TelemetryDatasource]:
        configured = store.get_telemetry_datasources()
        if configured:
            return configured
        return [
            TelemetryDatasource(kind="jaeger", url=settings.jaeger_api_url, label="default jaeger"),
            TelemetryDatasource(kind="prometheus", url=settings.prometheus_api_url, label="default prometheus"),
            TelemetryDatasource(kind="loki", url=settings.loki_api_url, label="default loki"),
        ]

    def sync_once(self) -> dict:
        # Fetch each signal independently so partial provider failures do not block sync.
        provider_status: dict[str, dict] = {}
        spans = []
        logs = []
        metrics = []

        datasources = self.get_effective_datasources()
        datasource_counts = {"jaeger": 0, "prometheus": 0, "loki": 0}

        for datasource in datasources:
            if not datasource.enabled:
                continue

            if datasource.kind == "jaeger":
                provider = JaegerProvider(datasource.url, timeout_seconds=settings.external_timeout_seconds)
                fetched_spans, status = self._safe_fetch(
                    provider_name=f"jaeger[{datasource_counts['jaeger']}]",
                    fetcher=lambda provider=provider: provider.fetch_spans(
                        lookback_seconds=settings.external_sync_window_seconds,
                        limit=settings.external_sync_limit,
                    ),
                )
                spans.extend(fetched_spans)
                status["kind"] = datasource.kind
                status["url"] = datasource.url
                status["label"] = datasource.label
                provider_status[f"jaeger[{datasource_counts['jaeger']}]"] = status
                datasource_counts["jaeger"] += 1
                continue

            if datasource.kind == "prometheus":
                provider = PrometheusProvider(datasource.url, timeout_seconds=settings.external_timeout_seconds)
                fetched_metrics, status = self._safe_fetch(
                    provider_name=f"prometheus[{datasource_counts['prometheus']}]",
                    fetcher=provider.fetch_metrics,
                )
                metrics.extend(fetched_metrics)
                status["kind"] = datasource.kind
                status["url"] = datasource.url
                status["label"] = datasource.label
                provider_status[f"prometheus[{datasource_counts['prometheus']}]"] = status
                datasource_counts["prometheus"] += 1
                continue

            if datasource.kind == "loki":
                provider = LokiProvider(datasource.url, timeout_seconds=settings.external_timeout_seconds)
                fetched_logs, status = self._safe_fetch(
                    provider_name=f"loki[{datasource_counts['loki']}]",
                    fetcher=lambda provider=provider: provider.fetch_logs(
                        lookback_seconds=settings.external_sync_window_seconds,
                        limit=settings.external_sync_limit,
                    ),
                )
                logs.extend(fetched_logs)
                status["kind"] = datasource.kind
                status["url"] = datasource.url
                status["label"] = datasource.label
                provider_status[f"loki[{datasource_counts['loki']}]"] = status
                datasource_counts["loki"] += 1

        store.replace_external_snapshot(spans=spans, logs=logs, metrics=metrics, provider_status=provider_status)

        return {
            "source_mode": "external",
            "synced": True,
            "spans": len(spans),
            "logs": len(logs),
            "metrics": len(metrics),
            "providers": provider_status,
            "datasources": [datasource.model_dump() for datasource in datasources],
            "synced_at": time.time(),
        }

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
