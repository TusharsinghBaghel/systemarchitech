from __future__ import annotations

from app.schemas.scenario import ScenarioRequest
from app.twin.twin_state import TwinState

#this module takes a base twin snapshot and a scenario payload, and returns a modified twin for simulation without touching the original.
def apply_scenario(base: TwinState, scenario: ScenarioRequest) -> TwinState:
    twin = TwinState(
        services={name: svc.model_copy(deep=True) for name, svc in base.services.items()},
        edges=[edge.model_copy(deep=True) for edge in base.edges],
    )

    for service_name, override in scenario.service_overrides.items():
        svc = twin.services.get(service_name)
        if not svc:
            continue
        if override.latency_multiplier is not None:
            svc.latency_distribution.mean *= override.latency_multiplier
            svc.latency_distribution.median *= override.latency_multiplier
            svc.latency_distribution.p95 *= override.latency_multiplier
            svc.latency_distribution.p99 *= override.latency_multiplier
        if override.error_rate_override is not None:
            svc.error_rate = max(0.0, min(1.0, override.error_rate_override))
        if override.concurrency_limit_override is not None:
            svc.concurrency_limit = max(1, override.concurrency_limit_override)

    for edge_key, override in scenario.edge_overrides.items():
        source, _, target = edge_key.partition("->")
        for edge in twin.edges:
            if edge.source_service != source or edge.target_service != target:
                continue
            if override.latency_multiplier is not None:
                edge.latency_distribution.mean *= override.latency_multiplier
                edge.latency_distribution.median *= override.latency_multiplier
                edge.latency_distribution.p95 *= override.latency_multiplier
                edge.latency_distribution.p99 *= override.latency_multiplier
            if override.call_probability_override is not None:
                edge.call_probability = max(0.0, min(1.0, override.call_probability_override))
            if override.error_rate_override is not None:
                edge.error_rate = max(0.0, min(1.0, override.error_rate_override))

    return twin
