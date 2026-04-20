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
uvicorn app.main:app --reload
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
