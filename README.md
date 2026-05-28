# OpenTelemetry Digital Twin MVP

This repository contains a greenfield MVP implementation with:

- FastAPI backend for ingestion, model building, and simulation
- React + TypeScript frontend for scenario input and result visualization

## Project Layout

- backend: API, model builder, digital twin state, simulation engine, tests
- frontend: React UI and API client

## Backend Run

```bash
cd backend
pip install -e .[dev]
uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

## Backend Test

```bash
cd backend
pytest -q
```

## Frontend Run

```bash
cd frontend
npm install
npm run dev
```

## Local Telemetry Test Producer (Separate From Product Logic)

Use the standalone script below to simulate user-side telemetry emission during development.
It is intentionally separate from backend business logic (model build, digital twin, simulation).

```bash
python scripts/stream_sample_telemetry.py --base-url http://127.0.0.1:8010
```

Simulate user-connected external providers (Jaeger/Prometheus/Loki via backend sync):

```bash
python scripts/stream_sample_telemetry.py --source-mode external
```

In external mode, the script only triggers sync. Cleaning, normalization, and interpretation
of Jaeger/Prometheus/Loki payloads are handled on the backend product side.

Run both direct ingest and external sync trigger together:

```bash
python scripts/stream_sample_telemetry.py --source-mode both
```

Send a single batch:

```bash
python scripts/stream_sample_telemetry.py --once
```

## Local Mock Observability APIs (GET Pull Testing)

Run a standalone mock server that exposes Jaeger, Prometheus, and Loki-like GET endpoints:

```bash
python scripts/mock_observability_apis.py --profile complex --port 18080
```

Then point backend external providers to this mock server and start backend in the same shell:

```powershell
$env:JAEGER_API_URL="http://127.0.0.1:18080/jaeger/api"
$env:PROMETHEUS_API_URL="http://127.0.0.1:18080/prometheus/api/v1"
$env:LOKI_API_URL="http://127.0.0.1:18080/loki"
uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

Trigger external pull mode:

```bash
python scripts/stream_sample_telemetry.py --source-mode external
```

## MVP API Endpoints

- GET /health
- POST /ingest/spans
- GET /activity/edges
- POST /model/build
- GET /model
- POST /simulate
- GET /simulate
- GET /simulate/{run_id}
- GET /scenarios/examples

## Notes

- Runtime state is in-memory for MVP.
- Optional persistence hooks can be added later without changing core API contracts.
