from dataclasses import dataclass

import httpx

from app.core.config import settings


class ResendError(Exception):
    pass


@dataclass(frozen=True)
class EmailMessage:
    email_type: str
    entity_id: int
    recipient: str
    subject: str
    text: str

    @property
    def idempotency_key(self) -> str:
        return f"ficmart:{self.email_type}:{self.entity_id}"


class ResendClient:
    def __init__(
        self,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._transport = transport

    async def send(self, message: EmailMessage) -> None:
        timeout = httpx.Timeout(
            settings.resend_timeout_seconds,
            connect=settings.resend_connect_timeout_seconds,
        )
        try:
            async with httpx.AsyncClient(
                base_url="https://api.resend.com",
                headers={
                    "Authorization": (
                        f"Bearer {settings.resend_api_key.get_secret_value()}"
                    ),
                    "Idempotency-Key": message.idempotency_key,
                },
                timeout=timeout,
                transport=self._transport,
            ) as client:
                response = await client.post(
                    "/emails",
                    json={
                        "from": settings.email_from_address,
                        "to": [message.recipient],
                        "subject": message.subject,
                        "text": message.text,
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError as error:
            raise ResendError from error
