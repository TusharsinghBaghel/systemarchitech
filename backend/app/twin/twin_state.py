from __future__ import annotations

from dataclasses import dataclass

from app.schemas.model import LearnedModel, ServiceEdgeModel, ServiceNodeModel


@dataclass
class TwinState:
    services: dict[str, ServiceNodeModel]
    edges: list[ServiceEdgeModel]

    @classmethod
    def from_model(cls, model: LearnedModel) -> "TwinState":
        services = {svc.service_name: svc.model_copy(deep=True) for svc in model.services}
        edges = [edge.model_copy(deep=True) for edge in model.edges]
        return cls(services=services, edges=edges)
