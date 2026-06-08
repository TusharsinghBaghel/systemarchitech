# TwinFana

### From Observability to Predictability

TwinFana is a Grafana-inspired observability dashboard that extends traditional monitoring with **digital twin-based service simulation**.

Instead of only answering:

> What happened?

TwinFana aims to answer:

> What will happen if I change something?

Using telemetry data from metrics, traces, and logs, TwinFana creates lightweight digital twins of deployed services and simulates their future behavior under different traffic patterns and operating conditions.

---

## Motivation

Modern observability platforms such as Grafana provide excellent visibility into system behavior through metrics, traces, and logs.

However, they primarily help answer questions about the **past and present**:

- Which service is failing?
- Where is latency increasing?
- What caused this incident?

TwinFana explores a different question:

- What happens if traffic increases by 2x?
- Which services become bottlenecks?
- How will latency propagate through the system?
- What is the impact of a failing dependency?

By leveraging historical telemetry data, TwinFana creates digital twins of services that can be used to simulate future scenarios.

---

## Architecture

TwinFana currently integrates with standard observability collectors:

- Prometheus (Metrics)
- Jaeger (Traces)
- Loki (Logs)

### Data Ingestion

```text
Prometheus ─┐
            ├──► TwinFana
Jaeger ─────┤
            │
Loki ───────┘
````

Telemetry data is used to:

* Build service dependency graphs
* Analyze request flow patterns
* Learn latency distributions
* Learn service health characteristics

---

## Service Graph Generation

Using traces and spans from Jaeger, TwinFana automatically constructs a service dependency graph.

```text
Client
  │
  ▼
Frontend
  │
  ├──► User Service
  │
  └──► Order Service
          │
          ▼
      Payment Service
```

The graph captures:

* Service dependencies
* Historical request flows
* Communication frequencies
* Upstream/downstream relationships

---

## Digital Twin Model

Each deployed service is represented by a lightweight digital twin.

A digital twin stores:

* Historical latency distributions
* Error-rate distributions
* Dependency relationships
* Request routing probabilities

The goal is not to reproduce service internals but to approximate observable runtime behavior using telemetry data.

---

## Simulation Engine

During simulation, requests are processed through an event-based simulation framework.

### Request Routing

Requests traverse the service graph based on probabilities learned from historical traces.

Example:

```text
Frontend
 ├─ 70% → User Service
 └─ 30% → Search Service
```

Simulation routing follows these learned probabilities.

### Latency Modeling

Each service twin estimates latency using historical latency distributions.

```text
Latency = f(historical latency distribution, scenario)
```

The current implementation uses expectation-based latency estimation.

### Error Modeling

Error characteristics can be modified through simulation scenarios.

Example:

```text
Payment Service

Normal Error Rate:     0.5%
Scenario Error Rate:   5%
```

This enables exploration of failure propagation and resilience behavior.

---

## Current Features

* Prometheus integration
* Jaeger integration
* Loki integration
* Service dependency graph generation
* Per-service observability dashboard
* Event-based simulation engine
* Historical flow probability modeling
* Scenario-based latency injection
* Scenario-based error injection

---

## ⚠️ Current Limitations

TwinFana is currently an MVP and makes several simplifying assumptions:

* Relies on third-party telemetry collectors. Can't take per-service telemetry endpoints
* Uses telemetry-derived approximations rather than complete system models
* Limited support for dynamic infrastructure changes
* Simplified latency prediction models
* Simplified request routing assumptions


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


## Notes

- Runtime state is in-memory for MVP.
- Optional persistence hooks can be added later without changing core API contracts.
