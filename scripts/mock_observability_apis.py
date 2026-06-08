#!/usr/bin/env python3
"""Local mock APIs for Jaeger, Prometheus, and Loki pull testing.

This script intentionally stays outside product backend logic.
It exposes GET endpoints that mimic common response shapes used by
provider adapters in this repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local mock observability APIs for pull-mode testing.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=18080, help="Port to bind (default: 18080)")
    parser.add_argument(
        "--profile",
        choices=["simple", "complex"],
        default="complex",
        help="Data complexity profile (default: complex)",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    return parser.parse_args()


def _stable_hex(*parts: object, length: int) -> str:
    data = "|".join(str(p) for p in parts).encode("utf-8")
    return hashlib.sha1(data).hexdigest()[:length]


class MockDataFactory:
    def __init__(self, profile: str, seed: int) -> None:
        self.profile = profile
        self.rng = random.Random(seed)
        if profile == "simple":
            self.graph = {
                "gateway": ["auth"],
                "auth": ["payments"],
                "payments": [],
            }
        else:
            self.graph = {
                "gateway": ["auth", "catalog", "cart", "search"],
                "auth": ["profile", "notifications"],
                "catalog": ["inventory", "recommendation", "catalog-db"],
                "cart": ["inventory", "payments"],
                "search": ["catalog", "recommendation"],
                "inventory": ["orders"],
                "payments": ["orders", "payments-db"],
                "profile": ["orders"],
                "recommendation": ["orders"],
                "notifications": ["orders"],
                "catalog-db": [],
                "payments-db": [],
                "orders": [],
            }
        self.services = sorted(self.graph.keys())
        self.entry = "gateway" if "gateway" in self.graph else self.services[0]

    def _trace_spans(self, trace_idx: int, start_us: int) -> tuple[str, dict[str, dict], list[dict]]:
        trace_id = _stable_hex("trace", trace_idx, start_us, length=32)
        processes = {
            f"p-{service}": {
                "serviceName": service,
                "tags": [{"key": "deployment.environment", "value": "prod"}],
            }
            for service in self.services
        }
        spans: list[dict] = []

        queue: list[tuple[str, str | None, int, int]] = [(self.entry, None, 0, start_us)]
        max_depth = 5 if self.profile == "complex" else 3

        while queue:
            service, parent_span_id, depth, scheduled_us = queue.pop(0)
            span_id = _stable_hex("span", trace_id, service, parent_span_id or "root", scheduled_us, length=16)
            duration_us = self.rng.randint(8_000, 120_000)
            # Vary span attributes so the model sees mixed RPC/HTTP traffic.
            tags = [{"key": "span.kind", "value": "SERVER"}]
            if parent_span_id is None:
                # Entry span: simulate HTTP ingress with varied methods.
                method = self.rng.choice(["GET", "POST", "PUT"])
                tags.append({"key": "http.method", "value": method})
            else:
                # Downstream calls: mostly HTTP, with rare RPC and an occasional DB branch.
                child_roll = self.rng.random()
                if service.endswith("-db"):
                    tags.append({"key": "db.system", "value": self.rng.choice(["postgresql", "mysql"])} )
                    tags.append({"key": "db.operation", "value": self.rng.choice(["SELECT", "UPDATE"])} )
                elif child_roll < 0.08:
                    tags.append({"key": "rpc.system", "value": "grpc"})
                    tags.append({"key": "rpc.service", "value": service})
                elif child_roll < 0.18:
                    tags.append({"key": "db.system", "value": self.rng.choice(["postgresql", "mysql"])} )
                    tags.append({"key": "db.operation", "value": self.rng.choice(["SELECT", "UPDATE"])} )
                else:
                    method = self.rng.choice(["GET", "POST"])
                    tags.append({"key": "http.method", "value": method})

            # Inject occasional errors to make traces realistic.
            if self.rng.random() < 0.08:
                tags.append({"key": "error", "value": True})
                tags.append({"key": "otel.status_code", "value": "ERROR"})

            span = {
                "traceID": trace_id,
                "spanID": span_id,
                "processID": f"p-{service}",
                "operationName": f"{service}.request",
                "startTime": scheduled_us,
                "duration": duration_us,
                "tags": tags,
                "references": [],
            }
            if parent_span_id:
                span["references"] = [{"refType": "CHILD_OF", "spanID": parent_span_id}]

            spans.append(span)

            if depth >= max_depth:
                continue
            downstream = self.graph.get(service, [])
            if not downstream:
                continue
            if self.rng.random() < 0.15:
                continue

            fan_out = 2 if self.profile == "complex" and depth <= 2 else 1
            chosen = self.rng.sample(downstream, k=min(fan_out, len(downstream)))
            for idx, child in enumerate(chosen):
                queue.append((child, span_id, depth + 1, scheduled_us + 2_000 + idx * 1_000))

        return trace_id, processes, spans

    def jaeger_payload(self, limit: int) -> dict:
        trace_count = max(1, min(limit, 12 if self.profile == "complex" else 4))
        now_us = time.time_ns() // 1000
        traces = []
        for idx in range(trace_count):
            trace_id, processes, spans = self._trace_spans(idx, now_us - idx * 50_000)
            traces.append({"traceID": trace_id, "processes": processes, "spans": spans})
        return {"data": traces}

    def prometheus_payload(self, query: str) -> dict:
        values = []
        now_s = int(time.time())

        # Emit a sample for every service with per-service variation.
        for idx, service in enumerate(self.services):
            # Small bias per-service so values vary across the graph.
            bias = (idx % 4) * 0.04
            if "process_cpu_seconds_total" in query:
                # CPU in 0..1 range; bias nudges some services slightly higher.
                value = min(0.99, round(self.rng.uniform(0.12, 0.65) + bias, 4))
            elif "process_resident_memory_bytes" in query:
                # Memory in bytes with modest per-service growth.
                base = self.rng.randint(120_000_000, 400_000_000)
                value = float(base + idx * 40_000_000)
            elif "otelcol_exporter_queue_size" in query:
                # Queue depth varies and can spike for some services.
                value = float(max(0, int(self.rng.gauss(30 + (idx % 5) * 10, 20))))
            else:
                value = round(self.rng.uniform(0.1, 1.0), 4)

            values.append(
                {
                    "metric": {
                        "service": service,
                        "deployment_environment": self.rng.choice(["prod", "staging"]),
                        "job": "mock-observability",
                        "instance": f"{service}-01",
                    },
                    "value": [now_s, str(value)],
                }
            )

        return {"status": "success", "data": {"resultType": "vector", "result": values}}

    def loki_payload(self, limit: int) -> dict:
        now_ns = time.time_ns()
        limit = max(1, min(limit, 120))
        streams = []
        per_service = max(2, limit // max(1, len(self.services)))

        for service_idx, service in enumerate(self.services):
            values = []
            for idx in range(per_service):
                ts = str(now_ns - idx * 1_000_000_000)
                sev_roll = self.rng.random()
                # Include trace ids sometimes to enable log->trace linking.
                trace_part = f" trace_id={_stable_hex(service, idx, length=16)}" if self.rng.random() < 0.3 else ""
                if sev_roll < 0.06:
                    msg = f"ERROR {service} timeout{trace_part}"
                elif sev_roll < 0.18:
                    msg = f"WARN {service} retrying downstream{trace_part}"
                elif sev_roll < 0.35:
                    msg = f"DEBUG {service} cache miss{trace_part}"
                else:
                    msg = f"INFO {service} request completed{trace_part}"
                values.append([ts, msg])

            streams.append(
                {
                    "stream": {
                        "service": service,
                        "deployment_environment": self.rng.choice(["prod", "staging"]),
                        "cluster": self.rng.choice(["mock-local", "mock-eu"]),
                    },
                    "values": values,
                }
            )

        return {"status": "success", "data": {"resultType": "streams", "result": streams}}


class MockObservabilityHandler(BaseHTTPRequestHandler):
    factory: MockDataFactory

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if parsed.path == "/jaeger/api/traces":
            limit = int(params.get("limit", ["200"])[0])
            self._json_response(200, self.factory.jaeger_payload(limit=limit))
            return

        if parsed.path == "/prometheus/api/v1/query":
            query = params.get("query", [""])[0]
            self._json_response(200, self.factory.prometheus_payload(query=query))
            return

        if parsed.path == "/loki/loki/api/v1/query_range":
            limit = int(params.get("limit", ["200"])[0])
            self._json_response(200, self.factory.loki_payload(limit=limit))
            return

        self._json_response(
            404,
            {
                "error": "not_found",
                "available_endpoints": [
                    "/jaeger/api/traces",
                    "/prometheus/api/v1/query",
                    "/loki/loki/api/v1/query_range",
                ],
            },
        )

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        # Keep logs concise and deterministic for local testing output.
        print(f"[{self.log_date_time_string()}] {self.address_string()} {format % args}")

    def _json_response(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    args = parse_args()

    factory = MockDataFactory(profile=args.profile, seed=args.seed)
    MockObservabilityHandler.factory = factory

    server = ThreadingHTTPServer((args.host, args.port), MockObservabilityHandler)

    print("Mock observability APIs running")
    print(f"Base: http://{args.host}:{args.port}")
    print(f"Profile: {args.profile}")
    print("Use these backend settings:")
    print(f"JAEGER_API_URL=http://{args.host}:{args.port}/jaeger/api")
    print(f"PROMETHEUS_API_URL=http://{args.host}:{args.port}/prometheus/api/v1")
    print(f"LOKI_API_URL=http://{args.host}:{args.port}/loki")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down mock observability APIs...")
    finally:
        server.server_close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
