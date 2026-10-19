"""Future asynchronous event boundary; no worker is running in Phase 1."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class BusinessEvent:
    event_id: str
    event_type: str
    order_id: str
    payload: dict
    schema_version: str = "1.0"


@dataclass(frozen=True)
class EventDeliveryResult:
    event_id: str
    accepted: bool
    duplicate: bool
    error: str | None = None


class EventWorker(Protocol):
    """Later implementations define persistent delivery, ordering and recovery."""

    def enqueue(self, event: BusinessEvent) -> EventDeliveryResult: ...

    def process_next(self) -> EventDeliveryResult | None: ...
