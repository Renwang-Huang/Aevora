"""Future payment boundary; Phase 1 does not execute payments."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class PaymentStatus(StrEnum):
    REQUESTED = "requested"
    CONFIRMED = "confirmed"
    FAILED = "failed"


@dataclass(frozen=True)
class PaymentIntent:
    order_id: str
    idempotency_key: str
    amount_minor_units: int
    currency: str


@dataclass(frozen=True)
class PaymentResult:
    idempotency_key: str
    status: PaymentStatus
    provider_reference: str | None = None
    error: str | None = None


class PaymentService(Protocol):
    """Implementations must persist idempotency keys before external side effects."""

    def request_payment(self, intent: PaymentIntent) -> PaymentResult: ...

    def get_payment(self, idempotency_key: str) -> PaymentResult: ...
