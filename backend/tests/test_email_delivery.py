import json
import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import settings
from app.emails.delivery import (
    send_new_order_email_impl,
    send_new_service_request_email_impl,
    send_order_cancelled_email_impl,
    send_order_confirmation_email_impl,
    send_payment_failed_email_impl,
    send_request_received_email_impl,
    send_welcome_email_impl,
)
from app.emails.resend import ResendClient, ResendError
from app.models import (
    MenuItem,
    MenuItemDay,
    Order,
    OrderItem,
    Payment,
    Service,
    ServiceRequest,
    User,
)

ALL_SEVEN_EMAIL_TYPES = (
    "welcome",
    "order_confirmation",
    "new_order",
    "payment_failed",
    "order_cancelled",
    "request_received",
    "new_service_request",
)


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class EmailEntities:
    sessions: async_sessionmaker[AsyncSession]
    user_id: int
    order_id: int
    payment_id: int
    service_id: int
    request_id: int


async def _email_entities(
    test_engine: AsyncEngine,
) -> EmailEntities:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    now = _now()
    async with session_factory.begin() as session:
        user = User(
            auth0_sub="auth0|email-test",
            email="customer@example.com",
            first_name="Ada",
            last_name="Lovelace",
            created_at=now,
        )
        menu_item = MenuItem(
            name="Jollof rice + chicken",
            category="Rice",
            price_minor=350_000,
            is_active=True,
            is_sold_out=False,
            created_at=now,
            updated_at=now,
        )
        menu_item.days = [MenuItemDay(weekday=1)]
        service = Service(
            name="Home cleaning",
            description="Deep clean",
            is_active=True,
            sort_order=1,
            created_at=now,
            updated_at=now,
        )
        session.add_all([user, menu_item, service])
        await session.flush()
        order = Order(
            user_id=user.id,
            status="paid",
            fulfillment_type="delivery",
            fulfillment_date=date(2026, 10, 5),
            contact={
                "name": "Ada",
                "phone": "+2348012345678",
                "address": "12 Example Street, Lekki",
            },
            notes="No pepper please",
            items_total_minor=350_000,
            delivery_fee_minor=150_000,
            total_minor=500_000,
            currency="NGN",
            created_at=now,
            updated_at=now,
        )
        session.add(order)
        await session.flush()
        session.add(
            OrderItem(
                order_id=order.id,
                menu_item_id=menu_item.id,
                name="Jollof rice + chicken",
                quantity=1,
                unit_price_minor=350_000,
            )
        )
        payment = Payment(
            order_id=order.id,
            provider="paystack",
            reference="email-payment-reference",
            amount_minor=500_000,
            currency="NGN",
            status="failed",
            created_at=now,
            updated_at=now,
        )
        service_request = ServiceRequest(
            user_id=user.id,
            service_id=service.id,
            preferred_date=date(2026, 10, 20),
            location="Lekki",
            details="Deep clean the 2 bedroom flat",
            contact_phone="+2348012345678",
            status="requested",
            created_at=now,
            updated_at=now,
        )
        session.add_all([payment, service_request])
        await session.flush()
        return EmailEntities(
            sessions=session_factory,
            user_id=user.id,
            order_id=order.id,
            payment_id=payment.id,
            service_id=service.id,
            request_id=service_request.id,
        )


async def test_all_seven_emails_go_out_with_deterministic_keys(
    test_engine: AsyncEngine,
) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"id": "resend-id"})

    entities = await _email_entities(test_engine)
    session_factory = entities.sessions
    client = ResendClient(transport=httpx.MockTransport(respond))

    await send_welcome_email_impl(
        entities.user_id, session_factory=session_factory, client=client
    )
    await send_order_confirmation_email_impl(
        entities.order_id, session_factory=session_factory, client=client
    )
    await send_new_order_email_impl(
        entities.order_id, session_factory=session_factory, client=client
    )
    await send_payment_failed_email_impl(
        entities.payment_id, session_factory=session_factory, client=client
    )
    await send_order_cancelled_email_impl(
        entities.order_id, session_factory=session_factory, client=client
    )
    await send_request_received_email_impl(
        entities.request_id, session_factory=session_factory, client=client
    )
    await send_new_service_request_email_impl(
        entities.request_id, session_factory=session_factory, client=client
    )

    assert len(requests) == 7
    assert [request.headers["Idempotency-Key"] for request in requests] == [
        f"damis:welcome:{entities.user_id}",
        f"damis:order_confirmation:{entities.order_id}",
        f"damis:new_order:{entities.order_id}",
        f"damis:payment_failed:{entities.payment_id}",
        f"damis:order_cancelled:{entities.order_id}",
        f"damis:request_received:{entities.request_id}",
        f"damis:new_service_request:{entities.request_id}",
    ]
    email_types = {
        key.split(":")[1]
        for key in (request.headers["Idempotency-Key"] for request in requests)
    }
    assert email_types == set(ALL_SEVEN_EMAIL_TYPES)


async def test_email_recipients_and_content(test_engine: AsyncEngine) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"id": "resend-id"})

    entities = await _email_entities(test_engine)
    session_factory = entities.sessions
    client = ResendClient(transport=httpx.MockTransport(respond))

    await send_welcome_email_impl(
        entities.user_id, session_factory=session_factory, client=client
    )
    await send_order_confirmation_email_impl(
        entities.order_id, session_factory=session_factory, client=client
    )
    await send_new_order_email_impl(
        entities.order_id, session_factory=session_factory, client=client
    )
    await send_payment_failed_email_impl(
        entities.payment_id, session_factory=session_factory, client=client
    )
    await send_order_cancelled_email_impl(
        entities.order_id, session_factory=session_factory, client=client
    )
    await send_request_received_email_impl(
        entities.request_id, session_factory=session_factory, client=client
    )
    await send_new_service_request_email_impl(
        entities.request_id, session_factory=session_factory, client=client
    )

    bodies = [json.loads(request.read()) for request in requests]
    assert all(body["from"] == settings.email_from_address for body in bodies)
    assert all(body["subject"] for body in bodies)

    assert bodies[0]["to"] == ["customer@example.com"]
    assert "Welcome to Dami's Lifestyle Services" in bodies[0]["subject"]
    assert "Hello Ada" in bodies[0]["text"]

    assert bodies[1]["to"] == ["customer@example.com"]
    assert "5,000.00 NGN" in bodies[1]["text"]
    assert "delivery" in bodies[1]["text"]

    assert bodies[2]["to"] == [settings.owner_notification_email]
    owner_alert = bodies[2]["text"]
    assert "1 x Jollof rice + chicken" in owner_alert
    assert "3,500.00 NGN" in owner_alert
    assert "5,000.00 NGN" in owner_alert
    assert "delivery on 2026-10-05" in owner_alert
    assert "No pepper please" in owner_alert
    assert "+2348012345678" in owner_alert
    assert "12 Example Street, Lekki" in owner_alert

    assert bodies[3]["to"] == ["customer@example.com"]
    assert "was marked failed" in bodies[3]["text"]

    assert bodies[4]["to"] == ["customer@example.com"]
    assert "has been cancelled" in bodies[4]["text"]

    assert bodies[5]["to"] == ["customer@example.com"]
    assert "Deep clean the 2 bedroom flat" in bodies[5]["text"]

    assert bodies[6]["to"] == [settings.owner_notification_email]
    assert "Home cleaning" in bodies[6]["text"]
    assert "Deep clean the 2 bedroom flat" in bodies[6]["text"]


async def test_every_request_authenticates_with_the_resend_key(
    test_engine: AsyncEngine,
) -> None:
    requests: list[httpx.Request] = []
    client = ResendClient(
        transport=httpx.MockTransport(
            lambda request: (
                requests.append(request),
                httpx.Response(200, json={"id": "resend-id"}),
            )[1]
        )
    )
    entities = await _email_entities(test_engine)

    await send_welcome_email_impl(
        entities.user_id,
        session_factory=entities.sessions,
        client=client,
    )

    assert requests[0].headers["Authorization"] == (
        f"Bearer {settings.resend_api_key.get_secret_value()}"
    )


@pytest.mark.parametrize(
    "email_type",
    ["welcome", "order_confirmation", "request_received", "new_order"],
)
async def test_a_missing_entity_sends_nothing(
    test_engine: AsyncEngine,
    email_type: str,
) -> None:
    requests: list[httpx.Request] = []
    client = ResendClient(
        transport=httpx.MockTransport(
            lambda request: (
                requests.append(request),
                httpx.Response(200, json={"id": "resend-id"}),
            )[1]
        )
    )
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    impls = {
        "welcome": send_welcome_email_impl,
        "order_confirmation": send_order_confirmation_email_impl,
        "request_received": send_request_received_email_impl,
        "new_order": send_new_order_email_impl,
    }

    await impls[email_type](9999, session_factory=session_factory, client=client)

    assert requests == []


async def test_resend_failure_logs_a_stable_event_without_response_details(
    test_engine: AsyncEngine,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def fail(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="private provider response")

    client = ResendClient(transport=httpx.MockTransport(fail))
    entities = await _email_entities(test_engine)

    with caplog.at_level(logging.ERROR, logger="app.emails.delivery"):
        with pytest.raises(ResendError):
            await send_welcome_email_impl(
                entities.user_id,
                session_factory=entities.sessions,
                client=client,
            )

    assert "email.send_failed" in caplog.text
    assert "private provider response" not in caplog.text
    assert settings.resend_api_key.get_secret_value() not in caplog.text
