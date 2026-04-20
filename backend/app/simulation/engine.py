from __future__ import annotations

import random
import uuid
from collections import defaultdict

from app.schemas.result import MetricsSummary, SimulationResult, TimeSlice
from app.schemas.scenario import ScenarioRequest
from app.simulation.distributions import summarize_latencies
from app.simulation.event_queue import EventQueue
from app.simulation.events import Event, EventType
from app.simulation.service_runtime import ServiceRuntime
from app.twin.router import Router
from app.twin.scenario_applier import apply_scenario
from app.twin.twin_state import TwinState


def _baseline_summary(base_twin: TwinState) -> MetricsSummary:
    # Empty-model guard: return a zeroed summary when no services are present.
    if not base_twin.services:
        return MetricsSummary(
            avg_latency_ms=0.0,
            p95_latency_ms=0.0,
            p99_latency_ms=0.0,
            failure_rate=0.0,
            completed_requests=0,
        )
    # Baseline is a coarse aggregate from the unmodified twin.
    means = [svc.latency_distribution.mean for svc in base_twin.services.values()]
    avg = sum(means) / len(means)
    return MetricsSummary(
        avg_latency_ms=avg,
        p95_latency_ms=max(svc.latency_distribution.p95 for svc in base_twin.services.values()),
        p99_latency_ms=max(svc.latency_distribution.p99 for svc in base_twin.services.values()),
        failure_rate=sum(svc.error_rate for svc in base_twin.services.values()) / len(base_twin.services),
        completed_requests=0,
    )


def run_simulation(base_twin: TwinState, scenario: ScenarioRequest) -> SimulationResult:
    # Each run gets a unique id and deterministic RNG (if seed is provided).
    run_id = str(uuid.uuid4())
    rng = random.Random(scenario.seed)

    # Apply scenario overrides on a copied twin, preserving baseline state.
    simulated_twin = apply_scenario(base_twin, scenario)
    baseline = _baseline_summary(base_twin)

    # If there is no graph to run, return baseline for both summaries.
    if not simulated_twin.services:
        return SimulationResult(run_id=run_id, baseline_summary=baseline, simulated_summary=baseline)

    # Use a deterministic entry service (lexicographically smallest name).
    entry_service = min(simulated_twin.services.keys())
    # Core simulation helpers: event scheduler, probabilistic router, per-service runtime state.
    event_queue = EventQueue()
    router = Router(simulated_twin.edges, rng)
    runtimes = {
        name: ServiceRuntime(
            service,
            rng,
            influence_strength=scenario.telemetry_influence_strength,
        )
        for name, service in simulated_twin.services.items()
    }

    # Convert traffic multiplier into number of external arrivals over the scenario window.
    total_requests = max(1, int(100 * scenario.traffic_multiplier))
    spacing_ms = max(1.0, (scenario.duration_seconds * 1000) / total_requests)
    # Seed the queue with ARRIVAL events targeting the entry service.
    for i in range(total_requests):
        event_queue.push(
            Event(
                time_ms=i * spacing_ms,
                event_type=EventType.ARRIVAL,
                request_id=f"req-{i}",
                service_name=entry_service,
            )
        )

    # Per-request lifecycle and aggregate counters used for final metrics.
    request_start: dict[str, float] = {}
    request_end: dict[str, float] = {}
    request_failed: set[str] = set()
    per_service_completed: dict[str, int] = defaultdict(int)
    # Timeline captures queue depth snapshots per service for each second bucket.
    timeline_queue: dict[int, dict[str, int]] = defaultdict(dict)

    # Main discrete-event loop: process events in chronological order.
    while len(event_queue) > 0:
        event = event_queue.pop()
        runtime = runtimes.get(event.service_name)
        # Skip events for services that are no longer present.
        if not runtime:
            continue

        # Track queue depth over time for diagnostics/visualization.
        second_bucket = int(event.time_ms // 1000)
        timeline_queue[second_bucket][event.service_name] = runtime.queue_depth()

        if event.event_type == EventType.ARRIVAL:
            # Record first-seen timestamp for end-to-end latency measurement.
            if event.request_id not in request_start:
                request_start[event.request_id] = event.time_ms

            if runtime.worker_available():
                # Start processing immediately and schedule its completion.
                runtime.acquire_worker()
                duration = runtime.sample_processing_duration_ms()
                event_queue.push(
                    Event(
                        time_ms=event.time_ms,
                        event_type=EventType.START_PROCESSING,
                        request_id=event.request_id,
                        service_name=event.service_name,
                    )
                )
                event_queue.push(
                    Event(
                        time_ms=event.time_ms + duration,
                        event_type=EventType.END_PROCESSING,
                        request_id=event.request_id,
                        service_name=event.service_name,
                    )
                )
            else:
                # No worker capacity: request waits in service-local queue.
                runtime.enqueue(event.request_id)

        elif event.event_type == EventType.END_PROCESSING:
            # Service finished one work item.
            runtime.release_worker()
            per_service_completed[event.service_name] += 1

            if runtime.should_fail():
                # Failure terminates this request path at current service.
                request_failed.add(event.request_id)
                request_end[event.request_id] = event.time_ms
                continue

            # Pull one queued request (if any) now that a worker is free.
            queued = runtime.dequeue()
            if queued is not None:
                event_queue.push(
                    Event(
                        time_ms=event.time_ms,
                        event_type=EventType.ARRIVAL,
                        request_id=queued,
                        service_name=event.service_name,
                    )
                )

            # Route successful completion to a downstream service hop.
            downstream = router.pick_next(event.service_name)
            if not downstream:
                # No outgoing edge means request completed its path.
                request_end[event.request_id] = event.time_ms
                continue

            # In current router model, downstream has one target, returned as list.
            for next_service in downstream:
                event_queue.push(
                    Event(
                        time_ms=event.time_ms,
                        event_type=EventType.ARRIVAL,
                        request_id=event.request_id,
                        service_name=next_service,
                    )
                )

    # Compute end-to-end latency statistics for completed requests.
    latencies = [request_end[rid] - start for rid, start in request_start.items() if rid in request_end]
    avg, p95, p99 = summarize_latencies(latencies)
    completed = len(request_end)
    failed = len(request_failed)
    # Failure rate is measured among completed terminal outcomes.
    failure_rate = (failed / completed) if completed else 0.0

    # Any service with residual queue depth at simulation end is flagged as bottleneck.
    bottlenecks = [
        name
        for name, runtime in runtimes.items()
        if runtime.queue_depth() > 0
    ]

    # Convert queue depth buckets into API response objects.
    timeline = [
        TimeSlice(second=second, queue_depth_by_service=queue_depths)
        for second, queue_depths in sorted(timeline_queue.items())
    ]

    # Final simulated summary used by UI and run history.
    simulated_summary = MetricsSummary(
        avg_latency_ms=avg,
        p95_latency_ms=p95,
        p99_latency_ms=p99,
        failure_rate=failure_rate,
        completed_requests=completed,
    )

    # Return full run payload with summaries and per-service diagnostics.
    return SimulationResult(
        run_id=run_id,
        baseline_summary=baseline,
        simulated_summary=simulated_summary,
        bottlenecks=bottlenecks,
        per_service_metrics={
            name: {
                "completed": count,
                "queue_depth": runtimes[name].queue_depth(),
            }
            for name, count in per_service_completed.items()
        },
        per_edge_metrics={},
        timeline=timeline,
    )
