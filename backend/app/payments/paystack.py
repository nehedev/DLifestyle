import hashlib
import hmac
import json
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import settings
from app.payments.protocol import (
    InitializedPayment,
    InitiatedRefund,
    PaymentEvent,
    PaymentProviderError,
    VerifiedPayment,
)

_API_BASE_URL = "https://api.paystack.co"
_ACTIONABLE_EVENTS = {
    "charge.success",
    "refund.processed",
    "refund.failed",
    "refund.needs-attention",
}


class PaystackProvider:
    name = "paystack"

    def __init__(
        self,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._transport = transport
        self._timeout = httpx.Timeout(
            settings.paystack_timeout_seconds,
            connect=settings.paystack_connect_timeout_seconds,
        )
        self._secret_key = settings.paystack_secret_key.get_secret_value()

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=_API_BASE_URL,
            headers={"Authorization": f"Bearer {self._secret_key}"},
            timeout=self._timeout,
            transport=self._transport,
        )

    async def _data(self, response: httpx.Response) -> Mapping[str, Any]:
        try:
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise PaymentProviderError from error
        if not isinstance(payload, dict) or payload.get("status") is not True:
            raise PaymentProviderError
        data = payload.get("data")
        if not isinstance(data, dict):
            raise PaymentProviderError
        return data

    async def initialize(
        self,
        *,
        reference: str,
        amount_minor: int,
        currency: str,
        email: str,
        callback_url: str,
    ) -> InitializedPayment:
        try:
            async with self._client() as client:
                response = await client.post(
                    "/transaction/initialize",
                    json={
                        "reference": reference,
                        "amount": amount_minor,
                        "currency": currency,
                        "email": email,
                        "callback_url": callback_url,
                    },
                )
            data = await self._data(response)
        except httpx.HTTPError as error:
            raise PaymentProviderError from error
        authorization_url = data.get("authorization_url")
        if not isinstance(authorization_url, str) or not authorization_url:
            raise PaymentProviderError
        return InitializedPayment(authorization_url=authorization_url)

    async def verify(self, reference: str) -> VerifiedPayment:
        try:
            async with self._client() as client:
                response = await client.get(
                    f"/transaction/verify/{quote(reference, safe='')}"
                )
            data = await self._data(response)
        except httpx.HTTPError as error:
            raise PaymentProviderError from error
        status = data.get("status")
        amount = data.get("amount")
        currency = data.get("currency")
        transaction_id = data.get("id")
        if (
            not isinstance(status, str)
            or isinstance(amount, bool)
            or not isinstance(amount, int)
            or not isinstance(currency, str)
        ):
            raise PaymentProviderError
        return VerifiedPayment(
            status=status,
            amount_minor=amount,
            currency=currency,
            provider_transaction_id=str(transaction_id)
            if isinstance(transaction_id, (int, str))
            and not isinstance(transaction_id, bool)
            else None,
        )

    async def refund(
        self,
        *,
        reference: str,
        amount_minor: int,
        currency: str,
    ) -> InitiatedRefund:
        try:
            async with self._client() as client:
                response = await client.post(
                    "/refund",
                    json={
                        "transaction": reference,
                        "amount": amount_minor,
                        "currency": currency,
                    },
                )
            if self._is_already_refunded_or_pending(response):
                return InitiatedRefund(status="pending")
            data = await self._data(response)
        except httpx.HTTPError as error:
            raise PaymentProviderError from error
        refund_status = data.get("status")
        if not isinstance(refund_status, str):
            raise PaymentProviderError
        return InitiatedRefund(status=refund_status)

    @staticmethod
    def _is_already_refunded_or_pending(response: httpx.Response) -> bool:
        try:
            payload = response.json()
        except ValueError:
            return False
        if not isinstance(payload, dict):
            return False
        data = payload.get("data")
        data_status = data.get("status") if isinstance(data, dict) else None
        if isinstance(data_status, str) and data_status in {"pending", "processed"}:
            return True
        message = payload.get("message")
        if not isinstance(message, str):
            return False
        normalized_message = message.casefold()
        return "already" in normalized_message and (
            "refund" in normalized_message or "pending" in normalized_message
        )

    def verify_webhook_signature(self, raw_body: bytes, signature: str) -> bool:
        expected = hmac.new(
            self._secret_key.encode(),
            raw_body,
            hashlib.sha512,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def parse_webhook(self, raw_body: bytes) -> PaymentEvent:
        try:
            payload = json.loads(raw_body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {"event_type": "ignored", "reference": None}
        if not isinstance(payload, dict):
            return {"event_type": "ignored", "reference": None}

        event_name = payload.get("event")
        if not isinstance(event_name, str):
            return {"event_type": "ignored", "reference": None}
        if event_name in {"refund.pending", "refund.processing"}:
            return {"event_type": "noop", "reference": None}
        if event_name not in _ACTIONABLE_EVENTS:
            return {"event_type": "ignored", "reference": None}

        data = payload.get("data")
        if not isinstance(data, dict):
            return {"event_type": "ignored", "reference": None}
        reference = self._extract_reference(data)
        return {"event_type": event_name, "reference": reference}

    @staticmethod
    def _extract_reference(data: Mapping[str, Any]) -> str | None:
        candidates: list[Any] = [
            data.get("reference"),
            data.get("transaction_reference"),
        ]
        transaction = data.get("transaction")
        if isinstance(transaction, dict):
            candidates.append(transaction.get("reference"))
        return next(
            (candidate for candidate in candidates if isinstance(candidate, str)),
            None,
        )
