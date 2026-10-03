import asyncio
import hashlib
import hmac
import json
from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.api.dependencies import CurrentUser, get_current_user, get_session
from app.core.config import settings
from app.main import app
from app.models import (
    MenuItem,
    MenuItemDay,
    Order,
    OrderItem,
    Payment,
    StoreSettings,
    User,
)
from app.payments.dependencies import get_payment_provider
from app.payments.paystack import PaystackProvider
from app.payments.protocol import (
    InitializedPayment,
    InitiatedRefund,
    PaymentEvent,
    PaymentProviderError,
    VerifiedPayment,
)
from app.services.payment_events import (
    process_payment_event_impl,
    refund_payment_impl,
)
from app.workers.celery_app import celery_app

BUSINESS_ZONE = ZoneInfo(settings.business_timezone)
DELIVERY_FEE_MINOR = 1500
CONTACT = {
    "name": "Ada Obi",
    "phone": "+2348012345678",
    "address": "12 Example Street, Lekki",
}


def business_today() -> date:
    return datetime.now(UTC).astimezone(BUSINESS_ZONE).date()


class FakePaymentProvider:
    name = "paystack"

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.session_factory = session_factory
        self.initialize_error = False
        self.initialize_statuses: list[str | None] = []
        self.initialize_references: list[str] = []
        self.verify_result: VerifiedPayment | None = None
        self.distinct_transaction_ids = False
        self.verify_references: list[str] = []
        self.refund_calls: list[tuple[str, int, str]] = []
        self.signature_valid = True
        self.parsed_event: PaymentEvent = {
            "event_type": "ignored",
            "reference": None,
        }

    async def initialize(
        self,
        *,
        reference: str,
        amount_minor: int,
        currency: str,
        email: str,
        callback_url: str,
    ) -> InitializedPayment:
        async with self.session_factory() as session:
            status = await session.scalar(
                select(Payment.status).where(Payment.reference == reference)
            )
        self.initialize_statuses.append(status)
        self.initialize_references.append(reference)
        if self.initialize_error:
            raise PaymentProviderError
        assert amount_minor > 0
        assert currency == "NGN"
        assert email == "orders-test@example.com"
        assert callback_url
        return InitializedPayment(authorization_url="https://checkout.example/pay")

    async def verify(self, reference: str) -> VerifiedPayment:
        self.verify_references.append(reference)
        if self.verify_result is None:
            raise AssertionError("test must set a verified gateway result")
        if self.distinct_transaction_ids:
            return replace(
                self.verify_result,
                provider_transaction_id=f"gateway-txn-{reference}",
            )
        return self.verify_result

    async def refund(
        self,
        *,
        reference: str,
        amount_minor: int,
        currency: str,
    ) -> InitiatedRefund:
        self.refund_calls.append((reference, amount_minor, currency))
        return InitiatedRefund(status="pending")

    def verify_webhook_signature(self, raw_body: bytes, signature: str) -> bool:
        return self.signature_valid and signature == "valid-signature"

    def parse_webhook(self, raw_body: bytes) -> PaymentEvent:
        return self.parsed_event


class PaymentTestClient:
    def __init__(
        self,
        client: AsyncClient,
        session_factory: async_sessionmaker[AsyncSession],
        user: User,
        provider: FakePaymentProvider,
        enqueued_tasks: list[tuple[str, list[int] | None]],
    ) -> None:
        self.client = client
        self.session_factory = session_factory
        self.user = user
        self.provider = provider
        self.enqueued_tasks = enqueued_tasks

    async def add_menu_item(
        self,
        *,
        name: str = "Payment dish",
        price_minor: int = 250_000,
        weekdays: tuple[int, ...] = (1, 2, 3, 4, 5, 6, 7),
        is_active: bool = True,
        is_sold_out: bool = False,
    ) -> int:
        async with self.session_factory.begin() as session:
            now = datetime.now(UTC)
            menu_item = MenuItem(
                name=name,
                price_minor=price_minor,
                is_active=is_active,
                is_sold_out=is_sold_out,
                created_at=now,
                updated_at=now,
            )
            session.add(menu_item)
            await session.flush()
            session.add_all(
                MenuItemDay(menu_item_id=menu_item.id, weekday=weekday)
                for weekday in weekdays
            )
            return menu_item.id


@pytest_asyncio.fixture
async def payment_client(
    test_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[PaymentTestClient]:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory.begin() as session:
        user = User(
            auth0_sub="auth0|payment-tests",
            email="orders-test@example.com",
            first_name="Ada",
            last_name="Obi",
            created_at=datetime.now(UTC),
        )
        session.add(user)
        await session.flush()
        user_id = user.id
        session.add(
            StoreSettings(
                id=1,
                delivery_fee_minor=DELIVERY_FEE_MINOR,
                order_cutoff_time=time(23, 59),
                max_advance_days=7,
                updated_at=datetime.now(UTC),
            )
        )

    detached_user = User(
        id=user_id,
        auth0_sub="auth0|payment-tests",
        email="orders-test@example.com",
        first_name="Ada",
        last_name="Obi",
        created_at=datetime.now(UTC),
    )
    provider = FakePaymentProvider(session_factory)
    enqueued_tasks: list[tuple[str, list[int] | None]] = []

    def capture_task(task_name: str, args: list[int] | None = None, **_: Any) -> None:
        enqueued_tasks.append((task_name, args))

    monkeypatch.setattr(celery_app, "send_task", capture_task)

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    async def override_current_user() -> CurrentUser:
        return CurrentUser(user=detached_user, roles=frozenset())

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_payment_provider] = lambda: provider
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            yield PaymentTestClient(
                client,
                session_factory,
                detached_user,
                provider,
                enqueued_tasks,
            )
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_payment_provider, None)


async def _create_order_and_attempt(
    payment_client: PaymentTestClient,
    *,
    quantity: int = 2,
    fulfillment_date: date | None = None,
) -> tuple[int, int, str]:
    menu_item_id = await payment_client.add_menu_item()
    order_response = await payment_client.client.post(
        "/api/v1/orders",
        json={
            "items": [{"menu_item_id": menu_item_id, "quantity": quantity}],
            "fulfillment_type": "delivery",
            "fulfillment_date": (
                fulfillment_date or business_today() + timedelta(days=1)
            ).isoformat(),
            "contact": CONTACT,
            "notes": None,
        },
    )
    assert order_response.status_code == 200, order_response.text
    order_id = order_response.json()["id"]

    pay_response = await payment_client.client.post(f"/api/v1/orders/{order_id}/pay")
    assert pay_response.status_code == 200
    assert pay_response.json() == {"authorization_url": "https://checkout.example/pay"}
    reference = payment_client.provider.initialize_references[-1]
    async with payment_client.session_factory() as session:
        payment = await session.scalar(
            select(Payment).where(Payment.reference == reference)
        )
    assert payment is not None
    return order_id, payment.id, reference


async def _get_order_and_payment(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    order_id: int,
    payment_id: int,
) -> tuple[Order, Payment]:
    async with session_factory() as session:
        order = await session.get(Order, order_id)
        payment = await session.get(Payment, payment_id)
    assert order is not None
    assert payment is not None
    return order, payment


def _success_result(
    *,
    amount_minor: int = 500_000 + DELIVERY_FEE_MINOR,
    currency: str = "NGN",
    status: str = "success",
) -> VerifiedPayment:
    return VerifiedPayment(
        status=status,
        amount_minor=amount_minor,
        currency=currency,
        provider_transaction_id="gateway-txn-1",
    )


async def _run_payment_event(
    payment_client: PaymentTestClient,
    event_type: str,
    reference: str,
    *,
    enqueue_refund: list[int] | None = None,
) -> None:
    await process_payment_event_impl(
        {"event_type": event_type, "reference": reference},
        session_factory=payment_client.session_factory,
        provider=payment_client.provider,
        enqueue_refund=(
            enqueue_refund.append if enqueue_refund is not None else lambda _: None
        ),
    )


async def test_pay_commits_initiated_attempt_before_provider_and_allows_retries(
    payment_client: PaymentTestClient,
) -> None:
    order_id, _, _ = await _create_order_and_attempt(payment_client)
    second = await payment_client.client.post(f"/api/v1/orders/{order_id}/pay")
    assert second.status_code == 200
    assert payment_client.provider.initialize_statuses == ["initiated", "initiated"]
    assert len(set(payment_client.provider.initialize_references)) == 2

    async with payment_client.session_factory() as session:
        payments = list(await session.scalars(select(Payment).order_by(Payment.id)))
    assert len(payments) == 2
    assert all(payment.status == "initiated" for payment in payments)


async def test_pay_initialization_failure_keeps_payment_initiated(
    payment_client: PaymentTestClient,
) -> None:
    menu_item_id = await payment_client.add_menu_item()
    order = await payment_client.client.post(
        "/api/v1/orders",
        json={
            "items": [{"menu_item_id": menu_item_id, "quantity": 1}],
            "fulfillment_type": "pickup",
            "fulfillment_date": (business_today() + timedelta(days=1)).isoformat(),
            "contact": {"name": "Ada Obi", "phone": "+2348012345678"},
            "notes": None,
        },
    )
    payment_client.provider.initialize_error = True

    response = await payment_client.client.post(
        f"/api/v1/orders/{order.json()['id']}/pay"
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "payment_initialization_failed"}
    async with payment_client.session_factory() as session:
        payment = await session.scalar(select(Payment))
    assert payment is not None
    assert payment.status == "initiated"


async def test_pay_requires_owned_pending_order(
    payment_client: PaymentTestClient,
) -> None:
    missing = await payment_client.client.post("/api/v1/orders/99999/pay")
    assert missing.status_code == 404

    order_id, _, _ = await _create_order_and_attempt(payment_client)
    async with payment_client.session_factory.begin() as session:
        await session.execute(
            update(Order).where(Order.id == order_id).values(status="paid")
        )
    response = await payment_client.client.post(f"/api/v1/orders/{order_id}/pay")
    assert response.status_code == 409
    assert response.json() == {"detail": "order_not_pending"}


async def test_webhook_signature_ignore_and_enqueue_paths(
    payment_client: PaymentTestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = b'{"event":"charge.success"}'

    payment_client.provider.signature_valid = False
    invalid_signature = await payment_client.client.post(
        "/api/v1/webhooks/paystack",
        content=body,
        headers={"x-paystack-signature": "bad"},
    )
    assert invalid_signature.status_code == 401
    assert invalid_signature.json() == {"detail": "invalid_signature"}

    payment_client.provider.signature_valid = True
    ignored = await payment_client.client.post(
        "/api/v1/webhooks/paystack",
        content=body,
        headers={"x-paystack-signature": "valid-signature"},
    )
    assert ignored.status_code == 200
    assert payment_client.enqueued_tasks == []

    payment_client.provider.parsed_event = {
        "event_type": "charge.success",
        "reference": "ref-queued",
    }
    queued_response = await payment_client.client.post(
        "/api/v1/webhooks/paystack",
        content=body,
        headers={"x-paystack-signature": "valid-signature"},
    )
    assert queued_response.status_code == 200
    assert payment_client.enqueued_tasks == [
        ("process_payment_event", [payment_client.provider.parsed_event])
    ]

    def fail_enqueue(*_: Any, **__: Any) -> None:
        raise RuntimeError("broker unavailable")

    monkeypatch.setattr(celery_app, "send_task", fail_enqueue)
    failed_enqueue = await payment_client.client.post(
        "/api/v1/webhooks/paystack",
        content=body,
        headers={"x-paystack-signature": "valid-signature"},
    )
    assert failed_enqueue.status_code == 503
    assert failed_enqueue.json() == {"detail": "webhook_enqueue_failed"}


async def test_verified_charge_success_marks_payment_and_order_paid_once(
    payment_client: PaymentTestClient,
) -> None:
    order_id, payment_id, reference = await _create_order_and_attempt(payment_client)
    payment_client.provider.verify_result = _success_result()
    queued_refunds: list[int] = []

    await _run_payment_event(
        payment_client,
        "charge.success",
        reference,
        enqueue_refund=queued_refunds,
    )
    await _run_payment_event(
        payment_client,
        "charge.success",
        reference,
        enqueue_refund=queued_refunds,
    )

    order, payment = await _get_order_and_payment(
        payment_client.session_factory,
        order_id=order_id,
        payment_id=payment_id,
    )
    assert order.status == "paid"
    assert payment.status == "succeeded"
    assert payment.provider_transaction_id == "gateway-txn-1"
    assert payment_client.provider.verify_references == [reference]
    assert queued_refunds == []
    assert payment_client.enqueued_tasks == [
        ("send_order_confirmation_email", [order_id]),
        ("send_new_order_email", [order_id]),
    ]


@pytest.mark.parametrize(
    "verified",
    [
        _success_result(amount_minor=1),
        _success_result(currency="USD"),
        _success_result(status="failed"),
    ],
)
async def test_gateway_mismatch_sets_needs_review_without_paying_order(
    payment_client: PaymentTestClient,
    verified: VerifiedPayment,
) -> None:
    order_id, payment_id, reference = await _create_order_and_attempt(payment_client)
    payment_client.provider.verify_result = verified

    await _run_payment_event(payment_client, "charge.success", reference)

    order, payment = await _get_order_and_payment(
        payment_client.session_factory,
        order_id=order_id,
        payment_id=payment_id,
    )
    assert payment.status == "needs_review"
    assert order.status == "pending"


async def test_unknown_payment_reference_is_ignored(
    payment_client: PaymentTestClient,
) -> None:
    payment_client.provider.verify_result = _success_result()
    await _run_payment_event(payment_client, "charge.success", "unknown-reference")
    assert payment_client.provider.verify_references == []


async def test_payment_failed_event_cancels_the_pending_order_once(
    payment_client: PaymentTestClient,
) -> None:
    order_id, payment_id, reference = await _create_order_and_attempt(payment_client)

    await _run_payment_event(payment_client, "payment.failed", reference)
    await _run_payment_event(payment_client, "payment.failed", reference)

    order, payment = await _get_order_and_payment(
        payment_client.session_factory,
        order_id=order_id,
        payment_id=payment_id,
    )
    assert order.status == "cancelled"
    assert payment.status == "failed"
    assert payment_client.enqueued_tasks == [
        ("send_payment_failed_email", [payment_id]),
        ("send_order_cancelled_email", [order_id]),
    ]


async def test_late_payment_reinstates_cancelled_order_when_still_fulfillable(
    payment_client: PaymentTestClient,
) -> None:
    order_id, payment_id, reference = await _create_order_and_attempt(payment_client)
    cancelled = await payment_client.client.post(f"/api/v1/orders/{order_id}/cancel")
    assert cancelled.status_code == 200
    payment_client.provider.verify_result = _success_result()

    await _run_payment_event(payment_client, "charge.success", reference)

    order, payment = await _get_order_and_payment(
        payment_client.session_factory,
        order_id=order_id,
        payment_id=payment_id,
    )
    assert order.status == "paid"
    assert payment.status == "succeeded"
    assert payment_client.provider.refund_calls == []


async def test_late_payment_after_the_cutoff_starts_a_refund(
    payment_client: PaymentTestClient,
) -> None:
    today = business_today()
    order_id, payment_id, reference = await _create_order_and_attempt(
        payment_client, fulfillment_date=today
    )
    cancelled = await payment_client.client.post(f"/api/v1/orders/{order_id}/cancel")
    assert cancelled.status_code == 200
    async with payment_client.session_factory.begin() as session:
        await session.execute(
            update(StoreSettings)
            .where(StoreSettings.id == 1)
            .values(order_cutoff_time=time(0, 0))
        )
    payment_client.provider.verify_result = _success_result()
    queued_refunds: list[int] = []

    await _run_payment_event(
        payment_client,
        "charge.success",
        reference,
        enqueue_refund=queued_refunds,
    )
    await refund_payment_impl(
        payment_id,
        session_factory=payment_client.session_factory,
        provider=payment_client.provider,
    )
    await _run_payment_event(payment_client, "refund.processed", reference)
    await _run_payment_event(payment_client, "refund.processed", reference)

    order, payment = await _get_order_and_payment(
        payment_client.session_factory,
        order_id=order_id,
        payment_id=payment_id,
    )
    assert queued_refunds == [payment_id]
    assert payment_client.provider.refund_calls == [
        (reference, 500_000 + DELIVERY_FEE_MINOR, "NGN")
    ]
    assert order.status == "cancelled"
    assert payment.status == "refunded"


async def test_late_payment_when_an_item_is_now_unavailable_starts_a_refund(
    payment_client: PaymentTestClient,
) -> None:
    menu_item_id = await payment_client.add_menu_item()
    order_response = await payment_client.client.post(
        "/api/v1/orders",
        json={
            "items": [{"menu_item_id": menu_item_id, "quantity": 1}],
            "fulfillment_type": "pickup",
            "fulfillment_date": (business_today() + timedelta(days=1)).isoformat(),
            "contact": {"name": "Ada Obi", "phone": "+2348012345678"},
            "notes": None,
        },
    )
    order_id = order_response.json()["id"]
    await payment_client.client.post(f"/api/v1/orders/{order_id}/pay")
    reference = payment_client.provider.initialize_references[-1]
    cancelled = await payment_client.client.post(f"/api/v1/orders/{order_id}/cancel")
    assert cancelled.status_code == 200
    async with payment_client.session_factory.begin() as session:
        await session.execute(
            update(MenuItem).where(MenuItem.id == menu_item_id).values(is_sold_out=True)
        )
    payment_client.provider.verify_result = _success_result(amount_minor=250_000)
    queued_refunds: list[int] = []

    await _run_payment_event(
        payment_client,
        "charge.success",
        reference,
        enqueue_refund=queued_refunds,
    )

    async with payment_client.session_factory() as session:
        order = await session.get(Order, order_id)
        payment = await session.scalar(
            select(Payment).where(Payment.reference == reference)
        )
    assert order is not None
    assert order.status == "cancelled"
    assert payment is not None
    assert payment.status == "refund_pending"
    assert queued_refunds == [payment.id]


@pytest.mark.parametrize("event_type", ["refund.failed", "refund.needs-attention"])
async def test_failed_refund_webhook_needs_review(
    payment_client: PaymentTestClient,
    event_type: str,
) -> None:
    _, payment_id, reference = await _create_order_and_attempt(payment_client)
    async with payment_client.session_factory.begin() as session:
        await session.execute(
            update(Payment)
            .where(Payment.id == payment_id)
            .values(status="refund_pending")
        )
    await _run_payment_event(payment_client, event_type, reference)
    await _run_payment_event(payment_client, event_type, reference)

    async with payment_client.session_factory() as session:
        payment = await session.get(Payment, payment_id)
    assert payment is not None
    assert payment.status == "needs_review"


async def test_duplicate_success_after_paid_order_needs_review_without_refund(
    payment_client: PaymentTestClient,
) -> None:
    order_id, payment_id, reference = await _create_order_and_attempt(payment_client)
    async with payment_client.session_factory.begin() as session:
        await session.execute(
            update(Order).where(Order.id == order_id).values(status="paid")
        )
    payment_client.provider.verify_result = _success_result()
    queued_refunds: list[int] = []

    await _run_payment_event(
        payment_client,
        "charge.success",
        reference,
        enqueue_refund=queued_refunds,
    )

    _, payment = await _get_order_and_payment(
        payment_client.session_factory,
        order_id=order_id,
        payment_id=payment_id,
    )
    assert payment.status == "needs_review"
    assert queued_refunds == []
    assert payment_client.provider.refund_calls == []


async def test_two_simultaneous_successes_yield_one_paid_and_one_needs_review(
    payment_client: PaymentTestClient,
) -> None:
    order_id, _, _ = await _create_order_and_attempt(payment_client)
    await payment_client.client.post(f"/api/v1/orders/{order_id}/pay")
    references = list(payment_client.provider.initialize_references)
    payment_client.provider.verify_result = _success_result()
    payment_client.provider.distinct_transaction_ids = True

    async def process_success(reference: str) -> None:
        await process_payment_event_impl(
            {"event_type": "charge.success", "reference": reference},
            session_factory=payment_client.session_factory,
            provider=payment_client.provider,
            enqueue_refund=lambda _: None,
        )

    async with asyncio.TaskGroup() as task_group:
        for reference in references:
            task_group.create_task(process_success(reference))

    async with payment_client.session_factory() as session:
        order = await session.get(Order, order_id)
        payments = list(
            await session.scalars(
                select(Payment).where(Payment.order_id == order_id).order_by(Payment.id)
            )
        )
    assert order is not None
    assert order.status == "paid"
    statuses = sorted(payment.status for payment in payments)
    assert statuses == ["needs_review", "succeeded"]


async def test_cancel_racing_verified_payment_is_consistent(
    payment_client: PaymentTestClient,
) -> None:
    order_id, payment_id, reference = await _create_order_and_attempt(payment_client)
    payment_client.provider.verify_result = _success_result()
    cancel_responses: list[httpx.Response] = []

    async def cancel_order() -> None:
        cancel_responses.append(
            await payment_client.client.post(f"/api/v1/orders/{order_id}/cancel")
        )

    async def process_success() -> None:
        await _run_payment_event(payment_client, "charge.success", reference)

    async with asyncio.TaskGroup() as task_group:
        task_group.create_task(cancel_order())
        task_group.create_task(process_success())

    order, payment = await _get_order_and_payment(
        payment_client.session_factory,
        order_id=order_id,
        payment_id=payment_id,
    )
    assert order.status == "paid"
    assert payment.status == "succeeded"
    assert cancel_responses[0].status_code in {200, 409}


async def test_paystack_adapter_maps_requests_responses_signature_and_events() -> None:
    seen_requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        if request.url.path == "/transaction/initialize":
            return httpx.Response(
                200,
                json={
                    "status": True,
                    "data": {"authorization_url": "https://checkout.example"},
                },
            )
        if request.url.path == "/transaction/verify/ref-123":
            return httpx.Response(
                200,
                json={
                    "status": True,
                    "data": {
                        "status": "success",
                        "amount": 500,
                        "currency": "NGN",
                        "id": 123,
                    },
                },
            )
        return httpx.Response(200, json={"status": True, "data": {"status": "pending"}})

    provider = PaystackProvider(transport=httpx.MockTransport(respond))
    initialized = await provider.initialize(
        reference="ref-123",
        amount_minor=500,
        currency="NGN",
        email="customer@example.com",
        callback_url="https://client.example/callback",
    )
    verified = await provider.verify("ref-123")
    refund = await provider.refund(
        reference="ref-123",
        amount_minor=500,
        currency="NGN",
    )

    assert initialized.authorization_url == "https://checkout.example"
    assert verified == VerifiedPayment(
        status="success",
        amount_minor=500,
        currency="NGN",
        provider_transaction_id="123",
    )
    assert refund == InitiatedRefund(status="pending")
    initialize_body = json.loads(seen_requests[0].content)
    refund_body = json.loads(seen_requests[2].content)
    assert initialize_body["amount"] == 500
    assert initialize_body["reference"] == "ref-123"
    assert refund_body["transaction"] == "ref-123"
    assert all(
        request.headers["Authorization"].startswith("Bearer ")
        for request in seen_requests
    )

    raw_body = b'{"event":"charge.success","data":{"reference":"ref-123"}}'
    signature = hmac.new(
        settings.paystack_secret_key.get_secret_value().encode(),
        raw_body,
        hashlib.sha512,
    ).hexdigest()
    assert provider.verify_webhook_signature(raw_body, signature)
    assert not provider.verify_webhook_signature(raw_body + b" ", signature)
    assert provider.parse_webhook(raw_body) == {
        "event_type": "charge.success",
        "reference": "ref-123",
    }
    assert provider.parse_webhook(
        b'{"event":"refund.processed","data":{"transaction_reference":"ref-123"}}'
    ) == {"event_type": "refund.processed", "reference": "ref-123"}
    assert provider.parse_webhook(b'{"event":"refund.processing"}') == {
        "event_type": "noop",
        "reference": None,
    }
    assert provider.parse_webhook(b'{"event":"transfer.success"}') == {
        "event_type": "ignored",
        "reference": None,
    }


async def test_paystack_already_pending_refund_response_is_idempotent() -> None:
    provider = PaystackProvider(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                409,
                json={"status": False, "message": "Refund already pending"},
            )
        )
    )
    result = await provider.refund(
        reference="ref-already-refunded",
        amount_minor=100,
        currency="NGN",
    )
    assert result == InitiatedRefund(status="pending")


async def test_a_menu_edit_does_not_change_the_stored_order_items(
    payment_client: PaymentTestClient,
) -> None:
    menu_item_id = await payment_client.add_menu_item(
        name="Snapshot dish", price_minor=300_000
    )
    order_response = await payment_client.client.post(
        "/api/v1/orders",
        json={
            "items": [{"menu_item_id": menu_item_id, "quantity": 2}],
            "fulfillment_type": "pickup",
            "fulfillment_date": (business_today() + timedelta(days=1)).isoformat(),
            "contact": {"name": "Ada Obi", "phone": "+2348012345678"},
            "notes": None,
        },
    )
    order_id = order_response.json()["id"]
    async with payment_client.session_factory.begin() as session:
        menu_item = await session.get(MenuItem, menu_item_id)
        assert menu_item is not None
        menu_item.price_minor = 900_000
        menu_item.name = "Renamed"

    detail = await payment_client.client.get(f"/api/v1/orders/{order_id}")
    assert detail.json()["items"] == [
        {"name": "Snapshot dish", "quantity": 2, "unit_price_minor": 300_000}
    ]
    async with payment_client.session_factory() as session:
        stored = list(
            await session.scalars(
                select(OrderItem).where(OrderItem.order_id == order_id)
            )
        )
    assert [item.name for item in stored] == ["Snapshot dish"]


async def test_pay_after_the_cutoff_is_rejected(
    payment_client: PaymentTestClient,
) -> None:
    today = business_today()
    order_id, _, _ = await _create_order_and_attempt(
        payment_client, fulfillment_date=today
    )
    references_before = list(payment_client.provider.initialize_references)
    async with payment_client.session_factory.begin() as session:
        await session.execute(
            update(StoreSettings)
            .where(StoreSettings.id == 1)
            .values(order_cutoff_time=time(0, 0))
        )

    response = await payment_client.client.post(f"/api/v1/orders/{order_id}/pay")

    assert response.status_code == 409
    assert response.json() == {"detail": "ordering_closed_for_date"}
    assert payment_client.provider.initialize_references == references_before


async def test_pay_is_rejected_before_any_payment_row_is_written(
    payment_client: PaymentTestClient,
) -> None:
    today = business_today()
    order_id, _, _ = await _create_order_and_attempt(
        payment_client, fulfillment_date=today
    )
    async with payment_client.session_factory.begin() as session:
        await session.execute(
            update(StoreSettings)
            .where(StoreSettings.id == 1)
            .values(order_cutoff_time=time(0, 0))
        )

    await payment_client.client.post(f"/api/v1/orders/{order_id}/pay")

    async with payment_client.session_factory() as session:
        payments = list(await session.scalars(select(Payment)))
    assert len(payments) == 1
    assert payments[0].status == "initiated"


async def test_pay_is_rejected_when_an_item_became_sold_out(
    payment_client: PaymentTestClient,
) -> None:
    menu_item_id = await payment_client.add_menu_item()
    order = await payment_client.client.post(
        "/api/v1/orders",
        json={
            "items": [{"menu_item_id": menu_item_id, "quantity": 1}],
            "fulfillment_type": "pickup",
            "fulfillment_date": (business_today() + timedelta(days=1)).isoformat(),
            "contact": {"name": "Ada Obi", "phone": "+2348012345678"},
            "notes": None,
        },
    )
    order_id = order.json()["id"]
    async with payment_client.session_factory.begin() as session:
        await session.execute(
            update(MenuItem).where(MenuItem.id == menu_item_id).values(is_sold_out=True)
        )

    response = await payment_client.client.post(f"/api/v1/orders/{order_id}/pay")

    assert response.status_code == 409
    assert response.json() == {"detail": {"unavailable_menu_item_ids": [menu_item_id]}}
    assert payment_client.provider.initialize_references == []


async def test_pay_is_rejected_when_an_item_is_deactivated(
    payment_client: PaymentTestClient,
) -> None:
    menu_item_id = await payment_client.add_menu_item()
    order = await payment_client.client.post(
        "/api/v1/orders",
        json={
            "items": [{"menu_item_id": menu_item_id, "quantity": 1}],
            "fulfillment_type": "pickup",
            "fulfillment_date": (business_today() + timedelta(days=1)).isoformat(),
            "contact": {"name": "Ada Obi", "phone": "+2348012345678"},
            "notes": None,
        },
    )
    order_id = order.json()["id"]
    async with payment_client.session_factory.begin() as session:
        await session.execute(
            update(MenuItem).where(MenuItem.id == menu_item_id).values(is_active=False)
        )

    response = await payment_client.client.post(f"/api/v1/orders/{order_id}/pay")

    assert response.status_code == 409
    assert response.json()["detail"] == {"unavailable_menu_item_ids": [menu_item_id]}


async def test_pay_is_rejected_when_the_weekday_is_no_longer_served(
    payment_client: PaymentTestClient,
) -> None:
    target = business_today() + timedelta(days=1)
    menu_item_id = await payment_client.add_menu_item(weekdays=(target.isoweekday(),))
    order = await payment_client.client.post(
        "/api/v1/orders",
        json={
            "items": [{"menu_item_id": menu_item_id, "quantity": 1}],
            "fulfillment_type": "pickup",
            "fulfillment_date": target.isoformat(),
            "contact": {"name": "Ada Obi", "phone": "+2348012345678"},
            "notes": None,
        },
    )
    order_id = order.json()["id"]
    async with payment_client.session_factory.begin() as session:
        await session.execute(
            delete(MenuItemDay).where(
                MenuItemDay.menu_item_id == menu_item_id,
                MenuItemDay.weekday == target.isoweekday(),
            )
        )

    response = await payment_client.client.post(f"/api/v1/orders/{order_id}/pay")

    assert response.status_code == 409
    assert response.json()["detail"] == {"unavailable_menu_item_ids": [menu_item_id]}


async def test_pay_still_works_before_the_cutoff(
    payment_client: PaymentTestClient,
) -> None:
    order_id, _, _ = await _create_order_and_attempt(payment_client)
    response = await payment_client.client.post(f"/api/v1/orders/{order_id}/pay")
    assert response.status_code == 200


async def test_a_pending_order_is_honoured_even_after_the_cutoff(
    payment_client: PaymentTestClient,
) -> None:
    today = business_today()
    order_id, payment_id, reference = await _create_order_and_attempt(
        payment_client, fulfillment_date=today
    )
    async with payment_client.session_factory.begin() as session:
        await session.execute(
            update(StoreSettings)
            .where(StoreSettings.id == 1)
            .values(order_cutoff_time=time(0, 0))
        )
    payment_client.provider.verify_result = _success_result()

    await _run_payment_event(payment_client, "charge.success", reference)

    order, payment = await _get_order_and_payment(
        payment_client.session_factory,
        order_id=order_id,
        payment_id=payment_id,
    )
    assert order.status == "paid"
    assert payment.status == "succeeded"


async def test_an_illegal_transition_logs_and_changes_nothing(
    payment_client: PaymentTestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    import logging

    _, payment_id, reference = await _create_order_and_attempt(payment_client)
    async with payment_client.session_factory.begin() as session:
        await session.execute(
            update(Payment)
            .where(Payment.id == payment_id)
            .values(status="needs_review")
        )
    payment_client.provider.verify_result = _success_result()

    with caplog.at_level(logging.ERROR, logger="app.services.payment_events"):
        await _run_payment_event(payment_client, "charge.success", reference)

    assert "payment.invalid_transition" in caplog.text
    async with payment_client.session_factory() as session:
        payment = await session.get(Payment, payment_id)
    assert payment is not None
    assert payment.status == "needs_review"


async def test_a_refund_webhook_on_a_wrong_status_logs_and_changes_nothing(
    payment_client: PaymentTestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    import logging

    _, payment_id, reference = await _create_order_and_attempt(payment_client)

    with caplog.at_level(logging.ERROR, logger="app.services.payment_events"):
        await _run_payment_event(payment_client, "refund.processed", reference)

    assert "payment.invalid_transition" in caplog.text
    async with payment_client.session_factory() as session:
        payment = await session.get(Payment, payment_id)
    assert payment is not None
    assert payment.status == "initiated"


async def test_refund_payment_calls_the_provider_once(
    payment_client: PaymentTestClient,
) -> None:
    order_id, payment_id, reference = await _create_order_and_attempt(payment_client)
    cancelled = await payment_client.client.post(f"/api/v1/orders/{order_id}/cancel")
    assert cancelled.status_code == 200
    async with payment_client.session_factory.begin() as session:
        await session.execute(
            update(Payment)
            .where(Payment.id == payment_id)
            .values(status="refund_pending")
        )

    await refund_payment_impl(
        payment_id,
        session_factory=payment_client.session_factory,
        provider=payment_client.provider,
    )

    assert payment_client.provider.refund_calls == [
        (reference, 500_000 + DELIVERY_FEE_MINOR, "NGN")
    ]
    async with payment_client.session_factory() as session:
        payment = await session.get(Payment, payment_id)
    assert payment is not None
    assert payment.status == "refund_pending"


async def test_refund_pending_and_processing_webhooks_change_nothing(
    payment_client: PaymentTestClient,
) -> None:
    _, payment_id, reference = await _create_order_and_attempt(payment_client)
    async with payment_client.session_factory.begin() as session:
        await session.execute(
            update(Payment)
            .where(Payment.id == payment_id)
            .values(status="refund_pending")
        )

    for event_type in ("refund.pending", "refund.processing"):
        await _run_payment_event(payment_client, event_type, reference)

    async with payment_client.session_factory() as session:
        payment = await session.get(Payment, payment_id)
    assert payment is not None
    assert payment.status == "refund_pending"


async def test_no_refund_is_started_for_a_duplicate_payment(
    payment_client: PaymentTestClient,
) -> None:
    order_id, payment_id, reference = await _create_order_and_attempt(payment_client)
    async with payment_client.session_factory.begin() as session:
        await session.execute(
            update(Order).where(Order.id == order_id).values(status="preparing")
        )
    payment_client.provider.verify_result = _success_result()
    queued_refunds: list[int] = []

    await _run_payment_event(
        payment_client, "charge.success", reference, enqueue_refund=queued_refunds
    )

    async with payment_client.session_factory() as session:
        payment = await session.get(Payment, payment_id)
    assert payment is not None
    assert payment.status == "needs_review"
    assert queued_refunds == []
    assert payment_client.provider.refund_calls == []
