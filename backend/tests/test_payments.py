import asyncio
import hashlib
import hmac
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.api.dependencies import get_current_user, get_session
from app.core.config import settings
from app.main import app
from app.models import Order, Payment, Product, User
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
from app.workers import payment_tasks

_ADDRESS = {
    "name": "Ada Lovelace",
    "phone": "+14155552671",
    "address_line_1": "1 Analytical Engine Way",
    "city": "London",
    "state": "London",
    "country": "GB",
}


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
    ) -> None:
        self.client = client
        self.session_factory = session_factory
        self.user = user
        self.provider = provider


@pytest_asyncio.fixture
async def payment_client(
    test_engine: AsyncEngine,
) -> AsyncIterator[PaymentTestClient]:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory.begin() as session:
        user = User(
            auth0_sub="auth0|payment-tests",
            email="orders-test@example.com",
            first_name="Ada",
            last_name="Lovelace",
            created_at=datetime.now(UTC),
        )
        session.add(user)
        await session.flush()

    user = User(
        id=user.id,
        auth0_sub=user.auth0_sub,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        created_at=user.created_at,
    )
    provider = FakePaymentProvider(session_factory)

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    async def override_current_user() -> User:
        return user

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_payment_provider] = lambda: provider
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            yield PaymentTestClient(client, session_factory, user, provider)
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_payment_provider, None)


async def _create_order_and_attempt(
    payment_client: PaymentTestClient,
    *,
    stock_quantity: int = 10,
    quantity: int = 2,
) -> tuple[int, int, int, str]:
    async with payment_client.session_factory.begin() as session:
        product = Product(
            name="Payment product",
            price_minor=250,
            stock_quantity=stock_quantity,
            is_active=True,
        )
        session.add(product)
        await session.flush()
        product_id = product.id

    order_response = await payment_client.client.post(
        "/api/v1/orders",
        json={
            "items": [{"product_id": product_id, "quantity": quantity}],
            "shipping_address": _ADDRESS,
        },
    )
    assert order_response.status_code == 200
    order_id = order_response.json()["id"]

    pay_response = await payment_client.client.post(f"/api/v1/orders/{order_id}/pay")
    assert pay_response.status_code == 200
    assert pay_response.json() == {"authorization_url": "https://checkout.example/pay"}
    reference = payment_client.provider.initialize_references[-1]
    async with payment_client.session_factory() as session:
        payment = await session.scalar(
            select(Payment).where(Payment.reference == reference)
        )
        order = await session.get(Order, order_id)
    assert payment is not None
    assert order is not None
    return order_id, payment.id, product_id, reference


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


async def _stock(
    session_factory: async_sessionmaker[AsyncSession],
    product_id: int,
) -> int:
    async with session_factory() as session:
        quantity = await session.scalar(
            select(Product.stock_quantity).where(Product.id == product_id)
        )
    assert quantity is not None
    return quantity


def _success_result(
    *,
    amount_minor: int = 500,
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
    order_id, _, _, _ = await _create_order_and_attempt(payment_client)
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
    async with payment_client.session_factory.begin() as session:
        product = Product(
            name="Initialization failure",
            price_minor=100,
            stock_quantity=2,
            is_active=True,
        )
        session.add(product)
        await session.flush()
        product_id = product.id
    order = await payment_client.client.post(
        "/api/v1/orders",
        json={
            "items": [{"product_id": product_id, "quantity": 1}],
            "shipping_address": _ADDRESS,
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

    order_id, _, _, _ = await _create_order_and_attempt(payment_client)
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
    queued: list[PaymentEvent] = []
    monkeypatch.setattr(payment_tasks.process_payment_event, "delay", queued.append)
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
    assert queued == []

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
    assert queued == [payment_client.provider.parsed_event]

    def fail_enqueue(event: PaymentEvent) -> None:
        raise RuntimeError("broker unavailable")

    monkeypatch.setattr(payment_tasks.process_payment_event, "delay", fail_enqueue)
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
    order_id, payment_id, product_id, reference = await _create_order_and_attempt(
        payment_client
    )
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
    assert await _stock(payment_client.session_factory, product_id) == 8
    assert payment_client.provider.verify_references == [reference]
    assert queued_refunds == []


@pytest.mark.parametrize(
    "verified",
    [
        _success_result(amount_minor=499),
        _success_result(currency="USD"),
        _success_result(status="failed"),
    ],
)
async def test_gateway_mismatch_sets_needs_review_without_paying_order(
    payment_client: PaymentTestClient,
    verified: VerifiedPayment,
) -> None:
    order_id, payment_id, _, reference = await _create_order_and_attempt(payment_client)
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


async def test_payment_failed_event_cancels_and_releases_stock_once(
    payment_client: PaymentTestClient,
) -> None:
    order_id, payment_id, product_id, reference = await _create_order_and_attempt(
        payment_client
    )
    assert await _stock(payment_client.session_factory, product_id) == 8

    await _run_payment_event(payment_client, "payment.failed", reference)
    await _run_payment_event(payment_client, "payment.failed", reference)

    order, payment = await _get_order_and_payment(
        payment_client.session_factory,
        order_id=order_id,
        payment_id=payment_id,
    )
    assert order.status == "cancelled"
    assert payment.status == "failed"
    assert await _stock(payment_client.session_factory, product_id) == 10


async def test_late_payment_reinstates_cancelled_order_when_stock_exists(
    payment_client: PaymentTestClient,
) -> None:
    order_id, payment_id, product_id, reference = await _create_order_and_attempt(
        payment_client
    )
    cancelled = await payment_client.client.post(f"/api/v1/orders/{order_id}/cancel")
    assert cancelled.status_code == 200
    assert await _stock(payment_client.session_factory, product_id) == 10
    payment_client.provider.verify_result = _success_result()

    await _run_payment_event(payment_client, "charge.success", reference)

    order, payment = await _get_order_and_payment(
        payment_client.session_factory,
        order_id=order_id,
        payment_id=payment_id,
    )
    assert order.status == "paid"
    assert payment.status == "succeeded"
    assert await _stock(payment_client.session_factory, product_id) == 8


async def test_late_payment_without_stock_starts_refund_and_refund_webhook_updates(
    payment_client: PaymentTestClient,
) -> None:
    order_id, payment_id, product_id, reference = await _create_order_and_attempt(
        payment_client
    )
    await payment_client.client.post(f"/api/v1/orders/{order_id}/cancel")
    async with payment_client.session_factory.begin() as session:
        await session.execute(
            update(Product).where(Product.id == product_id).values(stock_quantity=1)
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
    assert payment_client.provider.refund_calls == [(reference, 500, "NGN")]
    assert order.status == "cancelled"
    assert payment.status == "refunded"
    assert await _stock(payment_client.session_factory, product_id) == 1


@pytest.mark.parametrize("event_type", ["refund.failed", "refund.needs-attention"])
async def test_failed_refund_webhook_needs_review(
    payment_client: PaymentTestClient,
    event_type: str,
) -> None:
    order_id, payment_id, _, reference = await _create_order_and_attempt(payment_client)
    async with payment_client.session_factory.begin() as session:
        await session.execute(
            update(Payment)
            .where(Payment.id == payment_id)
            .values(status="refund_pending")
        )
    await _run_payment_event(payment_client, event_type, reference)
    await _run_payment_event(payment_client, event_type, reference)

    order, payment = await _get_order_and_payment(
        payment_client.session_factory,
        order_id=order_id,
        payment_id=payment_id,
    )
    assert order.status == "pending"
    assert payment.status == "needs_review"


async def test_duplicate_success_after_paid_order_needs_review_without_refund(
    payment_client: PaymentTestClient,
) -> None:
    order_id, payment_id, _, reference = await _create_order_and_attempt(payment_client)
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

    order, payment = await _get_order_and_payment(
        payment_client.session_factory,
        order_id=order_id,
        payment_id=payment_id,
    )
    assert order.status == "paid"
    assert payment.status == "needs_review"
    assert queued_refunds == []
    assert payment_client.provider.refund_calls == []


async def test_cancel_racing_verified_payment_is_consistent(
    payment_client: PaymentTestClient,
) -> None:
    order_id, payment_id, product_id, reference = await _create_order_and_attempt(
        payment_client
    )
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
    assert await _stock(payment_client.session_factory, product_id) == 8
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
