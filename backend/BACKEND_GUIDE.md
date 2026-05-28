# Backend Guide: Architecture and APIs

This document explains how the backend is structured, how data flows through it, and what each API endpoint does.

## 1. High-Level Architecture

The backend has four main responsibilities:

1. Ingest telemetry signals (spans, logs, metrics).
2. Build a service graph model from traces and enrich it with log/metric signals.
3. Run what-if simulations on that model.
4. Sync telemetry from external observability tools (Jaeger, Prometheus, Loki).

Core entrypoint:
- app startup and router registration: app/main.py

## 2. Module Layout

- app/api
  - HTTP routes grouped by domain (`ingest`, `model`, `simulate`, `telemetry`, etc).
- app/providers
  - External integrations for Jaeger/Prometheus/Loki.
- app/services
  - Cross-cutting orchestration (for example telemetry sync).
- app/ingestion
  - Validation and normalization of telemetry payloads.
- app/model_builder
  - Trace graph building and signal enrichment.
- app/simulation
  - Discrete-event simulation engine.
- app/storage
  - In-memory store and snapshot helpers.
- app/schemas
  - Pydantic contracts for payloads and outputs.
- app/twin
  - Twin state and routing used by simulation.
- app/activity
  - Edge activity counters for live traffic view.

## 3. Data Flow

### 3.1 Ingest -> Normalize -> Store

1. Client sends telemetry to:
   - POST /ingest/spans
   - POST /ingest/logs
   - POST /ingest/metrics
2. Each payload is validated and normalized into internal records.
3. Records are appended to MemoryStore.

Key files:
- app/api/ingest.py
- app/ingestion/normalize.py
- app/ingestion/log_normalize.py
- app/ingestion/metric_normalize.py
- app/storage/memory_store.py

### 3.2 Build Model

1. POST /model/build reads stored spans.
2. graph_builder builds service nodes and inter-service edges.
3. log_metric_builder enriches nodes with log and metric signals.
4. Learned model is saved in memory and returned via GET /model.

Key files:
- app/api/model.py
- app/model_builder/graph_builder.py
- app/model_builder/log_metric_builder.py
- app/schemas/model.py

### 3.3 Simulate

1. POST /simulate takes a ScenarioRequest.
2. TwinState is created from the learned model.
3. simulation/engine.py runs the discrete-event loop.
4. SimulationResult is stored and returned.
5. Results can be listed and fetched by run id.

Key files:
- app/api/simulate.py
- app/simulation/engine.py
- app/simulation/service_runtime.py
- app/schemas/scenario.py
- app/schemas/result.py

### 3.4 External Sync (Jaeger/Prometheus/Loki)

1. POST /telemetry/sync triggers one synchronization cycle.
2. TelemetrySyncService calls three providers:
   - JaegerProvider -> spans
   - PrometheusProvider -> metrics
   - LokiProvider -> logs
3. Store replaces current snapshot with synced external data.
4. GET /telemetry/status exposes provider health + snapshot counts.

Key files:
- app/api/telemetry.py
- app/services/telemetry_sync.py
- app/providers/jaeger.py
- app/providers/prometheus.py
- app/providers/loki.py
- app/config.py

## 4. API Reference

### 4.1 Health

- GET /health
- Purpose: liveness check.
- Response example:

```json
{
  "status": "ok"
}
```

### 4.2 Ingestion

#### POST /ingest/spans

- Body type: OTelSpanBatch
- Stores normalized SpanRecord entries.
- Response example:

```json
{
  "ingested_spans": 120,
  "trace_count": 25,
  "total_spans_stored": 1240
}
```

#### POST /ingest/logs

- Body type: OTelLogBatch
- Stores normalized LogRecord entries.
- Response example:

```json
{
  "ingested_logs": 80,
  "services_touched": 7,
  "total_logs_stored": 950
}
```

#### POST /ingest/metrics

- Body type: OTelMetricBatch
- Stores normalized MetricRecord entries.
- Response example:

```json
{
  "ingested_metrics": 60,
  "services_touched": 8,
  "total_metrics_stored": 540
}
```

### 4.3 Activity

#### GET /activity/edges

- Query:
  - window_seconds (1..30)
  - top_n (1..200)
- Purpose: recent inter-service edge activity.

### 4.4 Model

#### POST /model/build

- Requires spans in store.
- Builds and enriches model.
- Response example:

```json
{
  "service_count": 10,
  "edge_count": 14,
  "trace_count": 120,
  "span_count": 1100,
  "log_count": 900,
  "metric_count": 500
}
```

#### GET /model

- Returns latest learned model.
- 404 if model has not been built yet.

### 4.5 Simulation

#### POST /simulate

- Body type: ScenarioRequest
- Runs simulation and stores result.

#### GET /simulate

- Query: limit (1..200)
- Returns compact run history.

#### GET /simulate/{run_id}

- Returns full SimulationResult for one run.

#### GET /scenarios/examples

- Returns predefined scenario payload examples.

### 4.6 Telemetry

#### POST /telemetry/sync

- Triggers external sync from Jaeger, Prometheus, Loki.
- Returns synced item counts + per-provider status.

#### GET /telemetry/status

- Returns source mode, stored counts, sync metadata, provider status.

#### GET /telemetry/logs

- Query:
  - limit (default 100)
  - service_name (optional)
- Returns newest-first logs for UI.

#### GET /telemetry/metrics/live

- Query:
  - window_seconds (default 30)
- Returns per-service rolling averages for live metric cards.

## 5. Important Schemas

- Span payload/records: app/schemas/otel.py
- Log payload/records: app/schemas/log.py
- Metric payload/records: app/schemas/metric.py
- Learned model: app/schemas/model.py
- Scenario request: app/schemas/scenario.py
- Simulation result: app/schemas/result.py
- Edge activity response: app/schemas/activity.py

## 6. Operational Notes

1. Storage is in-memory; restarting the backend resets telemetry snapshots and learned model.
2. Simulation history is persisted to backend/data/simulation_runs.json.
3. External provider failures are isolated per provider in telemetry sync:
   - One provider can fail while others still sync.
4. Model build requires spans; logs/metrics enrich but do not replace trace graph construction.

## 7. Typical Workflow

1. Push telemetry (or trigger external sync).
2. Build model via POST /model/build.
3. Inspect model via GET /model.
4. Run scenario via POST /simulate.
5. Explore runs via GET /simulate and GET /simulate/{run_id}.
6. Keep telemetry fresh with POST /telemetry/sync.

## 8. Quick Start Commands

Run backend:

```bash
pip install -e .[dev]
uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

Run tests:

```bash
pytest -q
```
