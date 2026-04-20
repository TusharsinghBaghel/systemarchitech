from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EventType(str, Enum):
    ARRIVAL = "ARRIVAL"
    START_PROCESSING = "START_PROCESSING"
    END_PROCESSING = "END_PROCESSING"
    FORWARD = "FORWARD"
    FAIL = "FAIL"
    COMPLETE = "COMPLETE"


@dataclass(order=True)
class Event:
    time_ms: float
    event_type: EventType
    request_id: str
    service_name: str
