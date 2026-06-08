from fastapi.testclient import TestClient

from app.main import app
from app.storage.memory_store import store


client = TestClient(app)


INGEST_PAYLOAD = {
    "resource_spans": [
        {
            "resource": {
                "service.name": "api",
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
                            "name": "GET /login",
                            "kind": "SERVER",
                            "start_time_unix_nano": 0,
                            "end_time_unix_nano": 3_000_000,
                            "status_code": "OK",
                            "attributes": {"http.method": "GET"},
                        }
                    ],
                }
            ],
        },
        {
            "resource": {
                "service.name": "auth",
                "deployment.environment": "prod",
            },
            "scope_spans": [
                {
                    "scope": "io.opentelemetry.auto",
                    "spans": [
                        {
                            "trace_id": "t1",
                            "span_id": "s2",
                            "parent_span_id": "s1",
                            "name": "validate",
                            "kind": "SERVER",
                            "start_time_unix_nano": 3_100_000,
                            "end_time_unix_nano": 9_000_000,
                            "status_code": "OK",
                            "attributes": {"rpc.system": "grpc"},
                        }
                    ],
                }
            ],
        },
    ]
}


def setup_function() -> None:
    store.raw_spans.clear()
    store.learned_model = None
    store.simulation_runs.clear()
    store.edge_activity_buckets.clear()


def test_ingest_build_and_simulate_flow() -> None:
    ingest_res = client.post("/ingest/spans", json=INGEST_PAYLOAD)
    assert ingest_res.status_code == 200

    build_res = client.post("/model/build")
    assert build_res.status_code == 200

    model_res = client.get("/model")
    assert model_res.status_code == 200

    sim_res = client.post(
        "/simulate",
        json={
            "traffic_multiplier": 2.0,
            "duration_seconds": 60,
            "seed": 7,
            "service_overrides": {},
            "edge_overrides": {},
        },
    )
    assert sim_res.status_code == 200
    body = sim_res.json()
    assert "run_id" in body

    run_res = client.get(f"/simulate/{body['run_id']}")
    assert run_res.status_code == 200

    list_res = client.get("/simulate")
    assert list_res.status_code == 200
    runs = list_res.json()["runs"]
    assert any(run["run_id"] == body["run_id"] for run in runs)


def test_edge_activity_endpoint_reflects_ingest() -> None:
    ingest_res = client.post("/ingest/spans", json=INGEST_PAYLOAD)
    assert ingest_res.status_code == 200

    activity_res = client.get("/activity/edges?window_seconds=10&top_n=12")
    assert activity_res.status_code == 200
    payload = activity_res.json()

    assert payload["window_seconds"] == 10
    assert payload["top_n"] == 12
    assert len(payload["edges"]) >= 1

    edge = payload["edges"][0]
    assert edge["source_service"] == "api"
    assert edge["target_service"] == "auth"
    assert edge["call_type"] == "rpc"
    assert edge["activity_count"] >= 1
