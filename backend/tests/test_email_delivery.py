import logging
from datetime import UTC, date, datetime

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import settings
from app.emails.delivery import (
    send_order_cancelled_email_impl,
    send_order_confirmation_email_impl,
    send_payment_failed_email_impl,
    send_welcome_email_impl,
)
from app.emails.resend import ResendClient, ResendError
from app.models import Order, Payment, User


async def _email_entities(
    test_engine: AsyncEngine,
) -> tuple[async_sessionmaker[AsyncSession], int, int, int]:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(UTC)
    async with session_factory.begin() as session:
        user = User(
            auth0_sub="auth0|email-test",
            email="email-test@example.com",
            first_name="Ada",
            last_name="Lovelace",
            created_at=now,
        )
        session.add(user)
        await session.flush()
        order = Order(
            user_id=user.id,
            status="paid",
            fulfillment_type="pickup",
            fulfillment_date=date(2026, 10, 5),
            contact={"name": "Ada", "phone": "+2348012345678", "address": None},
            items_total_minor=1234,
            delivery_fee_minor=0,
            total_minor=1234,
            currency="NGN",
            created_at=now,
            updated_at=now,
        )
        session.add(order)
        await session.flush()
        payment = Payment(
            order_id=order.id,
            provider="paystack",
            reference="email-payment-reference",
            amount_minor=1234,
            currency="NGN",
            status="failed",
            created_at=now,
            updated_at=now,
        )
        session.add(payment)
        await session.flush()
        return session_factory, user.id, order.id, payment.id


async def test_four_email_tasks_use_resend_and_deterministic_keys(
    test_engine: AsyncEngine,
) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"id": "resend-id"})

    session_factory, user_id, order_id, payment_id = await _email_entities(test_engine)
    client = ResendClient(transport=httpx.MockTransport(respond))

    await send_welcome_email_impl(
        user_id,
        session_factory=session_factory,
        client=client,
    )
    await send_order_confirmation_email_impl(
        order_id,
        session_factory=session_factory,
        client=client,
    )
    await send_payment_failed_email_impl(
        payment_id,
        session_factory=session_factory,
        client=client,
    )
    await send_order_cancelled_email_impl(
        order_id,
        session_factory=session_factory,
        client=client,
    )

    assert [request.headers["Idempotency-Key"] for request in requests] == [
        f"ficmart:welcome:{user_id}",
        f"ficmart:order_confirmation:{order_id}",
        f"ficmart:payment_failed:{payment_id}",
        f"ficmart:order_cancelled:{order_id}",
    ]
    messages = [request.read().decode() for request in requests]
    assert all('"from"' in message for message in messages)
    assert all('"to":["email-test@example.com"]' in message for message in messages)
    assert "Welcome to Ficmart" in messages[0]
    assert "1234 NGN" in messages[1]
    assert "was marked failed" in messages[2]
    assert "has been cancelled" in messages[3]
    assert all(
        request.headers["Authorization"].startswith("Bearer ") for request in requests
    )
    assert all(
        request.headers["Authorization"]
        == f"Bearer {settings.resend_api_key.get_secret_value()}"
        for request in requests
    )


async def test_resend_failure_logs_stable_event_without_response_details(
    test_engine: AsyncEngine,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def fail(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="private provider response")

    client = ResendClient(transport=httpx.MockTransport(fail))
    session_factory, user_id, _, _ = await _email_entities(test_engine)

    with caplog.at_level(logging.ERROR, logger="app.emails.delivery"):
        with pytest.raises(ResendError):
            await send_welcome_email_impl(
                user_id,
                session_factory=session_factory,
                client=client,
            )

    assert "email.send_failed" in caplog.text
    assert "private provider response" not in caplog.text
