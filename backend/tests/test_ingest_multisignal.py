from fastapi.testclient import TestClient
import time

from app.main import app
from app.storage.memory_store import store


client = TestClient(app)


LOG_PAYLOAD = {
    "resource_logs": [
        {
            "resource": {
                "service.name": "gateway",
                "deployment.environment": "prod",
            },
            "scope_logs": [
                {
                    "scope": "io.opentelemetry.auto",
                    "records": [
                        {
                            "time_unix_nano": 1_000_000_000,
                            "severity_text": "ERROR",
                            "body": "timeout on upstream auth",
                            "attributes": {"component": "edge"},
                            "trace_id": "t1",
                            "span_id": "s1",
                        }
                    ],
                }
            ],
        }
    ]
}

METRIC_PAYLOAD = {
    "resource_metrics": [
        {
            "resource": {
                "service.name": "gateway",
                "deployment.environment": "prod",
            },
            "scope_metrics": [
                {
                    "scope": "io.opentelemetry.auto",
                    "records": [
                        {
                            "metric_name": "cpu.utilization",
                            "metric_type": "gauge",
                            "value": 0.83,
                            "time_unix_nano": 1_000_000_100,
                            "attributes": {},
                        },
                        {
                            "metric_name": "queue.depth",
                            "metric_type": "gauge",
                            "value": 42,
                            "time_unix_nano": 1_000_000_100,
                            "attributes": {},
                        },
                    ],
                }
            ],
        }
    ]
}

SPAN_PAYLOAD = {
    "resource_spans": [
        {
            "resource": {
                "service.name": "gateway",
                "deployment.environment": "prod",
            },
            "scope_spans": [
                {
                    "scope": "io.opentelemetry.auto",
                    "spans": [
                        {
                            "trace_id": "t1",
                            "span_id": "s1",
                            "parent_span_id": None,
                            "name": "GET /checkout",
                            "kind": "SERVER",
                            "start_time_unix_nano": 0,
                            "end_time_unix_nano": 3_000_000,
                            "status_code": "OK",
                            "attributes": {"http.method": "GET"},
                        }
                    ],
                }
            ],
        }
    ]
}


def setup_function() -> None:
    store.raw_spans.clear()
    store.raw_logs.clear()
    store.raw_metrics.clear()
    store.learned_model = None


def test_ingest_logs_metrics_and_model_enrichment() -> None:
    assert client.post("/ingest/spans", json=SPAN_PAYLOAD).status_code == 200

    logs_res = client.post("/ingest/logs", json=LOG_PAYLOAD)
    assert logs_res.status_code == 200
    assert logs_res.json()["ingested_logs"] == 1

    metrics_res = client.post("/ingest/metrics", json=METRIC_PAYLOAD)
    assert metrics_res.status_code == 200
    assert metrics_res.json()["ingested_metrics"] == 2

    build_res = client.post("/model/build")
    assert build_res.status_code == 200
    build_payload = build_res.json()
    assert build_payload["log_count"] == 1
    assert build_payload["metric_count"] == 2

    model_res = client.get("/model")
    assert model_res.status_code == 200
    services = model_res.json()["services"]
    assert len(services) == 1
    service = services[0]
    assert service["service_name"] == "gateway"
    assert service["log_error_rate"] >= 0.0
    assert service["live_cpu_utilization"] is not None


def test_telemetry_read_endpoints() -> None:
    now_ns = time.time_ns()
    metric_payload = {
        "resource_metrics": [
            {
                "resource": {
                    "service.name": "gateway",
                    "deployment.environment": "prod",
                },
                "scope_metrics": [
                    {
                        "scope": "io.opentelemetry.auto",
                        "records": [
                            {
                                "metric_name": "cpu.utilization",
                                "metric_type": "gauge",
                                "value": 0.81,
                                "time_unix_nano": now_ns,
                                "attributes": {},
                            }
                        ],
                    }
                ],
            }
        ]
    }

    client.post("/ingest/logs", json=LOG_PAYLOAD)
    client.post("/ingest/metrics", json=metric_payload)

    logs_res = client.get("/telemetry/logs?limit=10")
    assert logs_res.status_code == 200
    assert logs_res.json()["count"] >= 1

    metrics_res = client.get("/telemetry/metrics/live?window_seconds=120")
    assert metrics_res.status_code == 200
    payload = metrics_res.json()
    assert payload["window_seconds"] == 120
    assert "gateway" in payload["services"]
