from __future__ import annotations

from collections import defaultdict

from app.model_builder.stats_builder import distribution, error_rate, throughput_rps
from app.model_builder.trace_parser import group_spans_by_trace, map_span_by_id
from app.schemas.model import LearnedModel, ServiceEdgeModel, ServiceNodeModel
from app.schemas.span import SpanRecord


def classify_call_type(span: SpanRecord) -> str:
    attrs = span.attributes
    if any(key.startswith("http.") for key in attrs):
        return "http"
    if any(key.startswith("db.") for key in attrs):
        return "db"
    if any(key.startswith("rpc.") for key in attrs):
        return "rpc"
    if any(key.startswith("messaging.") for key in attrs):
        return "kafka"
    return "other"


def build_model(spans: list[SpanRecord]) -> LearnedModel:

    # group spans by service 
    by_service: dict[str, list[SpanRecord]] = defaultdict(list)
    for span in spans:
        by_service[span.service_name].append(span)

    # build service node models with basic stats of each service from time series data
    services: list[ServiceNodeModel] = []
    for service_name, service_spans in by_service.items():
        services.append(
            ServiceNodeModel(
                service_name=service_name,
                concurrency_limit=4,
                latency_distribution=distribution([s.duration_ms for s in service_spans]),
                error_rate=error_rate(service_spans),
                throughput_rps=throughput_rps(service_spans),
            )
        )

    # build service edge models with stats for each edge from time series data
    edge_durations: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    edge_error_samples: dict[tuple[str, str, str], list[SpanRecord]] = defaultdict(list)
    outgoing_counts: dict[str, int] = defaultdict(int)

    traces = group_spans_by_trace(spans)
    for trace_spans in traces.values():
        span_index = map_span_by_id(trace_spans)
        for span in trace_spans:
            if not span.parent_span_id:
                continue
            parent = span_index.get(span.parent_span_id)
            if not parent:
                continue
            if parent.service_name == span.service_name:
                continue
            call_type = classify_call_type(span)
            edge_key = (parent.service_name, span.service_name, call_type)
            edge_durations[edge_key].append(span.duration_ms)
            edge_error_samples[edge_key].append(span)
            outgoing_counts[parent.service_name] += 1

    edges: list[ServiceEdgeModel] = []
    for (source, target, call_type), durations in edge_durations.items():
        call_count = len(durations)
        total_outgoing = max(outgoing_counts[source], 1)
        edges.append(
            ServiceEdgeModel(
                source_service=source,
                target_service=target,
                call_type=call_type,
                latency_distribution=distribution(durations),
                call_probability=call_count / total_outgoing,
                error_rate=error_rate(edge_error_samples[(source, target, call_type)]),
            )
        )

    return LearnedModel(
        services=sorted(services, key=lambda s: s.service_name),
        edges=sorted(edges, key=lambda e: (e.source_service, e.target_service, e.call_type)),
        trace_count=len(traces),
        span_count=len(spans),
    )
