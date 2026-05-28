#!/usr/bin/env python3
"""Standalone test telemetry producer for local product testing.

This script is intentionally outside backend product logic.
It simulates user-side telemetry emission by pushing sample OTel-like payloads
into the backend ingest endpoints.

For external provider mode, this script only triggers backend sync.
All Jaeger/Prometheus/Loki cleaning, normalization, and interpretation stays
inside backend provider adapters and services.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
import urllib.error
import urllib.request
import uuid


TOPOLOGY_PRESETS: dict[str, dict[str, list[str]]] = {
    # Simple baseline for quick local checks.
    "linear3": {
        "gateway": ["auth"],
        "auth": ["payments"],
        "payments": [],
    },
    # Richer graph with fan-out and multiple downstream routes.
    "microservices10": {
        "gateway": ["auth", "catalog", "cart", "search"],
        "auth": ["profile", "notifications"],
        "catalog": ["inventory", "recommendation"],
        "cart": ["inventory", "payments"],
        "search": ["catalog", "recommendation"],
        "inventory": ["orders"],
        "payments": ["orders"],
        "profile": ["orders"],
        "recommendation": ["orders"],
        "notifications": ["orders"],
        "orders": [],
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Continuously simulate telemetry input for testing. "
            "Supports direct ingest payloads and external provider sync triggers."
        )
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8010",
        help="Backend base URL (default: http://127.0.0.1:8010)",
    )
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=2.0,
        help="Delay between telemetry batches (default: 2.0)",
    )
    parser.add_argument(
        "--environment",
        default="prod",
        help="deployment.environment value (default: prod)",
    )
    parser.add_argument(
        "--services",
        default=None,
        help=(
            "Optional comma-separated service chain override. "
            "When provided, preset topology is ignored and a linear chain is used."
        ),
    )
    parser.add_argument(
        "--topology-preset",
        choices=sorted(TOPOLOGY_PRESETS.keys()),
        default="microservices10",
        help="Topology preset used when --services is not provided (default: microservices10)",
    )
    parser.add_argument(
        "--traces-per-batch",
        type=int,
        default=8,
        help="Number of traces generated per direct batch (default: 8)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Send exactly one batch and exit",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible payload values (default: 42)",
    )
    parser.add_argument(
        "--source-mode",
        choices=["direct", "external", "both"],
        default="direct",
        help="Telemetry input mode: direct ingest, external sync trigger, or both (default: direct)",
    )
    return parser.parse_args()


def post_json(url: str, payload: dict) -> dict:
    raw = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=raw, method="POST")
    request.add_header("Content-Type", "application/json")

    with urllib.request.urlopen(request, timeout=15) as response:
        body = response.read().decode("utf-8")
        return json.loads(body) if body else {}


def hex_id(bytes_len: int) -> str:
    return uuid.uuid4().hex[: bytes_len * 2]


def build_linear_graph(services: list[str]) -> dict[str, list[str]]:
    graph: dict[str, list[str]] = {}
    for index, service_name in enumerate(services):
        graph[service_name] = [services[index + 1]] if index + 1 < len(services) else []
    return graph


def pick_entry_service(graph: dict[str, list[str]]) -> str:
    all_nodes = set(graph.keys())
    child_nodes = {child for targets in graph.values() for child in targets}
    roots = sorted(all_nodes - child_nodes)
    return roots[0] if roots else sorted(all_nodes)[0]


def build_trace_spans(
    graph: dict[str, list[str]],
    entry_service: str,
    start_ns: int,
) -> list[tuple[str, dict]]:
    trace_id = hex_id(16)
    max_depth = 5
    trace_spans: list[tuple[str, dict]] = []

    # (service, parent_span_id, depth, scheduled_start_ns)
    queue: list[tuple[str, str | None, int, int]] = [(entry_service, None, 0, start_ns)]

    while queue:
        service_name, parent_span_id, depth, span_start_ns = queue.pop(0)
        span_id = hex_id(8)
        duration_ms = random.uniform(7.0, 160.0)
        duration_ns = int(duration_ms * 1_000_000)

        attrs = {"http.method": "GET"} if parent_span_id is None else {"rpc.system": "grpc"}
        span = {
            "trace_id": trace_id,
            "span_id": span_id,
            "parent_span_id": parent_span_id,
            "name": f"{service_name}.request",
            "kind": "SERVER",
            "start_time_unix_nano": span_start_ns,
            "end_time_unix_nano": span_start_ns + duration_ns,
            "status_code": "ERROR" if random.random() < 0.06 else "OK",
            "attributes": attrs,
        }
        trace_spans.append((service_name, span))

        if depth >= max_depth:
            continue

        downstream = graph.get(service_name, [])
        if not downstream:
            continue

        # Keep realistic fan-out while avoiding explosive span counts.
        fan_out_cap = 2 if depth <= 2 else 1
        fan_out = min(len(downstream), fan_out_cap)
        if fan_out <= 0:
            continue

        if random.random() < 0.18:
            continue

        chosen = random.sample(downstream, fan_out)
        for index, child_service in enumerate(chosen):
            child_start = span_start_ns + int((2 + index * 2) * 1_000_000)
            queue.append((child_service, span_id, depth + 1, child_start))

    return trace_spans


def build_spans_payload(
    graph: dict[str, list[str]],
    services: list[str],
    entry_service: str,
    environment: str,
    now_ns: int,
    traces_per_batch: int,
) -> dict:
    spans_by_service: dict[str, list[dict]] = {service_name: [] for service_name in services}

    for trace_index in range(max(1, traces_per_batch)):
        trace_start_ns = now_ns + (trace_index * 1_000_000)
        trace_spans = build_trace_spans(
            graph=graph,
            entry_service=entry_service,
            start_ns=trace_start_ns,
        )
        for service_name, span in trace_spans:
            spans_by_service.setdefault(service_name, []).append(span)

    resource_spans = []
    for service_name in services:
        service_spans = spans_by_service.get(service_name, [])
        if not service_spans:
            continue
        resource_spans.append(
            {
                "resource": {
                    "service.name": service_name,
                    "deployment.environment": environment,
                },
                "scope_spans": [
                    {
                        "scope": "sample.streamer",
                        "spans": service_spans,
                    }
                ],
            }
        )

    return {"resource_spans": resource_spans}


def build_logs_payload(services: list[str], environment: str, now_ns: int) -> dict:
    resource_logs = []
    for service_name in services:
        severity = "ERROR" if random.random() < 0.08 else "INFO"
        body = (
            f"{service_name}: upstream timeout"
            if severity == "ERROR"
            else f"{service_name}: request completed"
        )
        resource_logs.append(
            {
                "resource": {
                    "service.name": service_name,
                    "deployment.environment": environment,
                },
                "scope_logs": [
                    {
                        "scope": "sample.streamer",
                        "records": [
                            {
                                "time_unix_nano": now_ns,
                                "severity_text": severity,
                                "body": body,
                                "attributes": {"source": "sample-streamer"},
                                "trace_id": None,
                                "span_id": None,
                            }
                        ],
                    }
                ],
            }
        )

    return {"resource_logs": resource_logs}


def build_metrics_payload(services: list[str], environment: str, now_ns: int) -> dict:
    resource_metrics = []

    for service_name in services:
        cpu = round(random.uniform(0.25, 0.95), 3)
        queue_depth = float(random.randint(0, 120))

        resource_metrics.append(
            {
                "resource": {
                    "service.name": service_name,
                    "deployment.environment": environment,
                },
                "scope_metrics": [
                    {
                        "scope": "sample.streamer",
                        "records": [
                            {
                                "metric_name": "cpu.utilization",
                                "metric_type": "gauge",
                                "value": cpu,
                                "time_unix_nano": now_ns,
                                "attributes": {"source": "sample-streamer"},
                            },
                            {
                                "metric_name": "queue.depth",
                                "metric_type": "gauge",
                                "value": queue_depth,
                                "time_unix_nano": now_ns,
                                "attributes": {"source": "sample-streamer"},
                            },
                        ],
                    }
                ],
            }
        )

    return {"resource_metrics": resource_metrics}


def run_once(
    base_url: str,
    services: list[str],
    graph: dict[str, list[str]],
    entry_service: str,
    environment: str,
    traces_per_batch: int,
) -> int:
    now_ns = time.time_ns()

    spans_payload = build_spans_payload(
        graph=graph,
        services=services,
        entry_service=entry_service,
        environment=environment,
        now_ns=now_ns,
        traces_per_batch=traces_per_batch,
    )
    logs_payload = build_logs_payload(services=services, environment=environment, now_ns=now_ns)
    metrics_payload = build_metrics_payload(services=services, environment=environment, now_ns=now_ns)

    try:
        spans_res = post_json(f"{base_url}/ingest/spans", spans_payload)
        logs_res = post_json(f"{base_url}/ingest/logs", logs_payload)
        metrics_res = post_json(f"{base_url}/ingest/metrics", metrics_payload)

        print(
            "sent",
            json.dumps(
                {
                    "mode": "direct",
                    "services": len(services),
                    "traces": max(1, traces_per_batch),
                    "spans": spans_res.get("ingested_spans"),
                    "logs": logs_res.get("ingested_logs"),
                    "metrics": metrics_res.get("ingested_metrics"),
                }
            ),
        )
        return 0
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code} from backend: {body}")
        return 1
    except urllib.error.URLError as exc:
        print(f"Could not reach backend at {base_url}: {exc.reason}")
        return 1


def run_external_sync_once(base_url: str) -> int:
    # External mode intentionally delegates all provider parsing/normalization
    # to product-side backend code. The harness only issues a sync trigger.
    try:
        sync_res = post_json(f"{base_url}/telemetry/sync", payload={})

        print(
            "sent",
            json.dumps(
                {
                    "mode": "external",
                    "spans": sync_res.get("spans"),
                    "logs": sync_res.get("logs"),
                    "metrics": sync_res.get("metrics"),
                    "providers": sync_res.get("providers", {}),
                }
            ),
        )
        return 0
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code} from backend: {body}")
        return 1
    except urllib.error.URLError as exc:
        print(f"Could not reach backend at {base_url}: {exc.reason}")
        return 1


def run_once_by_mode(
    base_url: str,
    services: list[str],
    graph: dict[str, list[str]],
    entry_service: str,
    environment: str,
    source_mode: str,
    traces_per_batch: int,
) -> int:
    if source_mode == "direct":
        return run_once(
            base_url=base_url,
            services=services,
            graph=graph,
            entry_service=entry_service,
            environment=environment,
            traces_per_batch=traces_per_batch,
        )

    if source_mode == "external":
        return run_external_sync_once(base_url=base_url)

    # both
    rc = run_once(
        base_url=base_url,
        services=services,
        graph=graph,
        entry_service=entry_service,
        environment=environment,
        traces_per_batch=traces_per_batch,
    )
    if rc != 0:
        return rc
    return run_external_sync_once(base_url=base_url)


def main() -> int:
    args = parse_args()
    random.seed(args.seed)

    base_url = args.base_url.rstrip("/")

    if args.services:
        services = [part.strip() for part in args.services.split(",") if part.strip()]
        graph = build_linear_graph(services)
    else:
        graph = TOPOLOGY_PRESETS[args.topology_preset]
        services = sorted(graph.keys())

    if len(services) < 2:
        print("Please provide at least two services in --services")
        return 1

    entry_service = pick_entry_service(graph)

    if args.once:
        return run_once_by_mode(
            base_url=base_url,
            services=services,
            graph=graph,
            entry_service=entry_service,
            environment=args.environment,
            source_mode=args.source_mode,
            traces_per_batch=args.traces_per_batch,
        )

    print("Starting continuous sample telemetry stream...")
    print(
        f"target={base_url}, services={len(services)}, entry={entry_service}, "
        f"mode={args.source_mode}, traces_per_batch={max(1, args.traces_per_batch)}, "
        f"interval={args.interval_seconds}s"
    )

    while True:
        rc = run_once_by_mode(
            base_url=base_url,
            services=services,
            graph=graph,
            entry_service=entry_service,
            environment=args.environment,
            source_mode=args.source_mode,
            traces_per_batch=args.traces_per_batch,
        )
        if rc != 0:
            return rc
        time.sleep(max(0.1, args.interval_seconds))


if __name__ == "__main__":
    sys.exit(main())
