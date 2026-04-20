from fastapi.testclient import TestClient

from app.main import app
from app.storage.memory_store import store


client = TestClient(app)


def setup_function() -> None:
    store.raw_spans.clear()
    store.raw_logs.clear()
    store.raw_metrics.clear()


def test_external_sync_attempts_provider_pull() -> None:
    res = client.post("/telemetry/sync")
    assert res.status_code == 200
    body = res.json()
    assert body["synced"] is True
    assert body["source_mode"] == "external"
    assert "providers" in body


def test_telemetry_status_endpoint() -> None:
    res = client.get("/telemetry/status")
    assert res.status_code == 200
    payload = res.json()
    assert "counts" in payload
    assert payload["source_mode"] == "external"
