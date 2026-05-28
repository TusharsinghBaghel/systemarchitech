from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.api.activity import router as activity_router
from app.api.health import router as health_router
from app.api.ingest import router as ingest_router
from app.api.model import router as model_router
from app.api.simulate import router as simulate_router
from app.api.telemetry import router as telemetry_router
from app.config import settings

app = FastAPI(title="OpenTelemetry Digital Twin MVP", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(ingest_router)
app.include_router(activity_router)
app.include_router(model_router)
app.include_router(simulate_router)
app.include_router(telemetry_router)


if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.api_host, port=settings.api_port, reload=True)
