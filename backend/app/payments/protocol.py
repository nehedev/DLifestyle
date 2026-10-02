from dataclasses import dataclass
from typing import Protocol, TypedDict


class PaymentEvent(TypedDict):
    event_type: str
    reference: str | None


@dataclass(frozen=True)
class InitializedPayment:
    authorization_url: str


@dataclass(frozen=True)
class VerifiedPayment:
    status: str
    amount_minor: int
    currency: str
    provider_transaction_id: str | None


@dataclass(frozen=True)
class InitiatedRefund:
    status: str


class PaymentProviderError(Exception):
    pass


class PaymentProvider(Protocol):
    name: str

    async def initialize(
        self,
        *,
        reference: str,
        amount_minor: int,
        currency: str,
        email: str,
        callback_url: str,
    ) -> InitializedPayment: ...

    async def verify(self, reference: str) -> VerifiedPayment: ...

    async def refund(
        self,
        *,
        reference: str,
        amount_minor: int,
        currency: str,
    ) -> InitiatedRefund: ...

    def verify_webhook_signature(self, raw_body: bytes, signature: str) -> bool: ...

    def parse_webhook(self, raw_body: bytes) -> PaymentEvent: ...
