from __future__ import annotations

import random
from collections import deque
from typing import Literal

from app.schemas.model import ServiceNodeModel

#TODO: The service runtime is not an actual digital twin which learns from historical data 
# and updates its behavior over time. Instead, it is a wrapper around the static service profile that 
# applies the learned biases and simulates request processing with latency and failure sampling. In a 
# more advanced implementation, the runtime could incorporate feedback loops to adjust its parameters 
# based on observed conditions during the simulation, allowing for dynamic adaptation and more realistic 
# modeling of service behavior under varying loads and telemetry signals.

class ServiceRuntime:
    # Runtime wrapper for one service node: tracks workers/queue and samples
    # latency/failures using the learned model plus telemetry influence.
    def __init__(
        self,
        service: ServiceNodeModel,
        rng: random.Random,
        # Global knob for how strongly telemetry biases should affect behavior.
        influence_strength: Literal["none", "low", "medium", "high"] = "medium",
    ) -> None:
        # Static service profile (baseline latency/error + computed biases).
        self.service = service
        # Shared RNG keeps simulation reproducible when a seed is provided.
        self._rng = rng
        # Number of in-flight requests currently using service workers.
        self._busy_workers = 0
        # FIFO queue of waiting request ids when all workers are busy.
        self._queue: deque[str] = deque()
        # Global knob for how strongly telemetry biases should affect behavior.
        self._influence_strength = influence_strength

    def worker_available(self) -> bool:
        #each worker can handle one request at a time, 
        # Effective capacity is never below 1 even if config is invalid.
        #max no of workers is equal to the concurrency limit, 
        return self._busy_workers < max(1, self.service.concurrency_limit)

    def acquire_worker(self) -> None:
        # Reserve one worker when request processing starts.
        self._busy_workers += 1

    def release_worker(self) -> None:
        # Release one worker when processing ends, clamped to avoid negatives.
        self._busy_workers = max(0, self._busy_workers - 1)

    def enqueue(self, request_id: str) -> None:
        # Push request to waiting queue when no worker is available.
        self._queue.append(request_id)

    def dequeue(self) -> str | None:
        # Pop next waiting request in FIFO order.
        if not self._queue:
            return None
        return self._queue.popleft()
    
    

    def queue_depth(self) -> int:
        # Queue depth is used for bottleneck reporting in simulation results.
        #equal to the no of waiting requests, not including the ones currently being processed by workers.
        return len(self._queue)

    def sample_processing_duration_ms(self) -> float:
        # Baseline distribution learned from traces; floor avoids degenerate values.
        mean = max(0.1, self.service.latency_distribution.mean)
        stddev = max(0.1, self.service.latency_distribution.stddev)
        # Scenario-selected influence strength scales telemetry-derived bias.
        strength = self._strength_factor()
        # Bias inflates processing time to reflect current stress conditions.
        influenced_mean = mean * (1.0 + (self.service.simulation_latency_bias * strength))
        # Sample actual processing duration and clamp to positive minimum.
        return max(0.1, self._rng.gauss(influenced_mean, stddev))

    def should_fail(self) -> bool:
        # Combine baseline error with telemetry-derived additional risk.
        strength = self._strength_factor()
        fail_rate = self.service.error_rate + (self.service.simulation_error_bias * strength)
        # Bernoulli trial with fail probability clamped to [0, 1].
        return self._rng.random() < max(0.0, min(1.0, fail_rate))

    def _strength_factor(self) -> float:
        # Maps scenario setting to numeric multiplier used by bias terms.
        if self._influence_strength == "none":
            return 0.0
        if self._influence_strength == "low":
            return 0.25
        if self._influence_strength == "high":
            return 1.0
        return 0.5
