from __future__ import annotations

from app.schemas.metric import MetricRecord, OTelMetricBatch


def normalize_metric_batch(batch: OTelMetricBatch) -> list[MetricRecord]:
    normalized: list[MetricRecord] = []
    for resource_metric in batch.resource_metrics:
        service_name = resource_metric.resource.service_name
        environment = resource_metric.resource.deployment_environment
        for scope_metrics in resource_metric.scope_metrics:
            for record in scope_metrics.records:
                normalized.append(
                    MetricRecord(
                        service_name=service_name,
                        deployment_environment=environment,
                        metric_name=record.metric_name,
                        metric_type=record.metric_type,
                        value=record.value,
                        timestamp_unix_nano=record.time_unix_nano,
                        attributes=record.attributes,
                    )
                )
    return normalized
