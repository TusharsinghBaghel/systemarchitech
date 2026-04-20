from __future__ import annotations

import heapq

from app.simulation.events import Event


class EventQueue:
    def __init__(self) -> None:
        self._heap: list[Event] = []

    def push(self, event: Event) -> None:
        heapq.heappush(self._heap, event)

    def pop(self) -> Event:
        return heapq.heappop(self._heap)

    def __len__(self) -> int:
        return len(self._heap)
