from __future__ import annotations

import random

from app.schemas.model import ServiceEdgeModel

#The Router class chooses the next service hop during simulation, based on learned edge call probabilities.
class Router:
    def __init__(self, edges: list[ServiceEdgeModel], rng: random.Random) -> None:
        self._rng = rng
        self._edges_by_source: dict[str, list[ServiceEdgeModel]] = {}
        for edge in edges:
            self._edges_by_source.setdefault(edge.source_service, []).append(edge)

    def pick_next(self, source_service: str) -> list[str]:
        candidates = self._edges_by_source.get(source_service, [])
        if not candidates:
            return []
        roll = self._rng.random()
        cumulative = 0.0
        for edge in candidates:
            cumulative += max(0.0, edge.call_probability)
            if roll <= cumulative:
                return [edge.target_service]
        return []
