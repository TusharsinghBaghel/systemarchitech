from fastapi import APIRouter, HTTPException

from app.schemas.scenario import ScenarioRequest
from app.simulation.engine import run_simulation
from app.storage.memory_store import store
from app.twin.twin_state import TwinState

router = APIRouter(tags=["simulate"])


@router.post("/simulate")
def simulate(scenario: ScenarioRequest) -> dict:
    if not store.learned_model:
        raise HTTPException(status_code=400, detail="Build a model before simulation")
    twin = TwinState.from_model(store.learned_model)
    result = run_simulation(twin, scenario)
    store.add_simulation_run(result)
    return result.model_dump()


@router.get("/simulate")
def list_simulations(limit: int = 20) -> dict:
    bounded_limit = max(1, min(limit, 200))
    runs = list(store.simulation_runs.values())
    selected_runs = list(reversed(runs[-bounded_limit:]))
    return {
        "runs": [
            {
                "run_id": run.run_id,
                "baseline_summary": run.baseline_summary.model_dump(),
                "simulated_summary": run.simulated_summary.model_dump(),
                "bottlenecks": run.bottlenecks,
            }
            for run in selected_runs
        ]
    }


@router.get("/simulate/{run_id}")
def get_simulation(run_id: str) -> dict:
    result = store.simulation_runs.get(run_id)
    if not result:
        raise HTTPException(status_code=404, detail="Run not found")
    return result.model_dump()


@router.get("/scenarios/examples")
def scenario_examples() -> dict:
    return {
        "examples": [
            {
                "name": "2x traffic",
                "payload": {
                    "traffic_multiplier": 2.0,
                    "duration_seconds": 120,
                    "seed": 42,
                    "service_overrides": {},
                    "edge_overrides": {},
                },
            },
            {
                "name": "DB slowdown",
                "payload": {
                    "traffic_multiplier": 1.0,
                    "duration_seconds": 120,
                    "seed": 42,
                    "service_overrides": {
                        "db-service": {
                            "latency_multiplier": 2.0,
                        }
                    },
                    "edge_overrides": {},
                },
            },
        ]
    }
