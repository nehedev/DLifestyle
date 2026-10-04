import os
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection as SyncConnection
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_TEST_SETTINGS = {
    "DATABASE_URL": "postgresql+asyncpg://ficmart:ficmart@localhost:5432/ficmart",
    "REDIS_URL": "redis://localhost:6379/0",
    "GOOGLE_CLIENT_ID": "test-client-id.apps.googleusercontent.com",
    "JWKS_CACHE_TTL_SECONDS": "3600",
    "JWKS_TIMEOUT_SECONDS": "5",
    "CURRENCY": "NGN",
    "BUSINESS_TIMEZONE": "Africa/Lagos",
    "PAYMENT_PROVIDER": "paystack",
    "PAYSTACK_SECRET_KEY": "sk_test_placeholder",
    "PAYSTACK_CONNECT_TIMEOUT_SECONDS": "5",
    "PAYSTACK_TIMEOUT_SECONDS": "10",
    "PAYMENT_CALLBACK_URL": "http://localhost:5173/payment/callback",
    "CORS_ORIGINS": '["http://localhost:5173"]',
    "RESEND_API_KEY": "re_placeholder",
    "RESEND_CONNECT_TIMEOUT_SECONDS": "5",
    "RESEND_TIMEOUT_SECONDS": "10",
    "EMAIL_FROM_ADDRESS": "Dami's Lifestyle Services <noreply@example.com>",
    "OWNER_NOTIFICATION_EMAIL": "owner@example.com",
    "CLOUDINARY_CLOUD_NAME": "test-cloud",
    "CLOUDINARY_API_KEY": "test-key",
    "CLOUDINARY_API_SECRET": "test-secret",
    "CLOUDINARY_UPLOAD_FOLDER": "damis-test",
    "PENDING_ORDER_TIMEOUT_MINUTES": "15",
    "EXPIRY_JOB_INTERVAL_MINUTES": "5",
    "CELERY_TASK_MAX_RETRIES": "5",
    "CELERY_RETRY_BACKOFF_MAX_SECONDS": "600",
}
for variable, value in _TEST_SETTINGS.items():
    os.environ.setdefault(variable, value)

BUSINESS_ZONE = ZoneInfo(_TEST_SETTINGS["BUSINESS_TIMEZONE"])
DELIVERY_FEE_MINOR = 1500
MAX_ADVANCE_DAYS = 7
CUTOFF = time(16, 0)
ORDER_CONTACT = {
    "name": "Ada Obi",
    "phone": "+2348012345678",
    "address": "12 Example Street, Lekki",
}
PICKUP_CONTACT = {"name": "Ada Obi", "phone": "+2348012345678"}


def pytest_configure() -> None:
    for variable, value in _TEST_SETTINGS.items():
        os.environ.setdefault(variable, value)


def business_today() -> date:
    return datetime.now(UTC).astimezone(BUSINESS_ZONE).date()


@pytest_asyncio.fixture(scope="session")
async def test_engine() -> AsyncIterator[AsyncEngine]:
    test_database_url = os.environ.get("TEST_DATABASE_URL")
    if not test_database_url:
        pytest.fail("TEST_DATABASE_URL must be set to a dedicated PostgreSQL database")

    parsed_test_url = make_url(test_database_url)
    application_database_url = os.environ["DATABASE_URL"]
    parsed_application_url = make_url(application_database_url)
    if parsed_test_url == parsed_application_url:
        pytest.fail("TEST_DATABASE_URL must differ from DATABASE_URL")
    if parsed_test_url.database == parsed_application_url.database:
        pytest.fail("TEST_DATABASE_URL must use a different database name")
    if parsed_test_url.database is None:
        pytest.fail("TEST_DATABASE_URL must include a database name")

    admin_url = parsed_test_url.set(database="postgres")
    admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    async with admin_engine.connect() as connection:
        database_exists = await connection.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :database_name"),
            {"database_name": parsed_test_url.database},
        )
        if database_exists is None:
            database_identifier = (
                admin_engine.sync_engine.dialect.identifier_preparer.quote_identifier(
                    parsed_test_url.database
                )
            )
            await connection.exec_driver_sql(f"CREATE DATABASE {database_identifier}")
    await admin_engine.dispose()

    engine = create_async_engine(test_database_url)
    from app.db.base import Base

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def truncate_test_database(test_engine: AsyncEngine) -> None:
    def truncate_tables(connection: SyncConnection) -> None:
        table_names = inspect(connection).get_table_names()
        if not table_names:
            return
        preparer = connection.dialect.identifier_preparer
        identifiers = ", ".join(preparer.quote(name) for name in table_names)
        connection.exec_driver_sql(
            f"TRUNCATE TABLE {identifiers} RESTART IDENTITY CASCADE"
        )

    async with test_engine.begin() as connection:
        await connection.run_sync(truncate_tables)


@dataclass
class OrderTestClient:
    client: AsyncClient
    session_factory: async_sessionmaker[AsyncSession]
    user_id: int
    user: Any
    enqueued_tasks: list[tuple[str, list[int] | None]] = field(default_factory=list)

    async def configure_store(
        self,
        *,
        delivery_fee_minor: int = DELIVERY_FEE_MINOR,
        cutoff: time = CUTOFF,
        max_advance_days: int = MAX_ADVANCE_DAYS,
    ) -> None:
        from app.models import StoreSettings

        async with self.session_factory.begin() as session:
            session.add(
                StoreSettings(
                    id=1,
                    delivery_fee_minor=delivery_fee_minor,
                    order_cutoff_time=cutoff,
                    max_advance_days=max_advance_days,
                    updated_at=datetime.now(UTC),
                )
            )

    async def add_menu_item(
        self,
        *,
        name: str = "Jollof rice + chicken",
        price_minor: int = 350_000,
        weekdays: tuple[int, ...] = (1, 2, 3, 4, 5, 6, 7),
        is_active: bool = True,
        is_sold_out: bool = False,
        category: str = "Rice",
    ) -> int:
        from app.models import MenuItem, MenuItemDay

        async with self.session_factory.begin() as session:
            now = datetime.now(UTC)
            menu_item = MenuItem(
                name=name,
                category=category,
                price_minor=price_minor,
                is_active=is_active,
                is_sold_out=is_sold_out,
                created_at=now,
                updated_at=now,
            )
            menu_item.days = [MenuItemDay(weekday=weekday) for weekday in weekdays]
            session.add(menu_item)
            await session.flush()
            return menu_item.id


def order_payload(
    menu_item_ids: list[int],
    *,
    fulfillment_type: str = "delivery",
    fulfillment_date: date | None = None,
    contact: dict[str, Any] | None = None,
    notes: str | None = None,
    quantities: list[int] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:

    quantities = quantities or [1] * len(menu_item_ids)
    payload: dict[str, Any] = {
        "items": [
            {"menu_item_id": menu_item_id, "quantity": quantity}
            for menu_item_id, quantity in zip(menu_item_ids, quantities, strict=True)
        ],
        "fulfillment_type": fulfillment_type,
        "fulfillment_date": (
            fulfillment_date or (business_today() + timedelta(days=1))
        ).isoformat(),
        "contact": dict(ORDER_CONTACT) if contact is None else contact,
        "notes": notes,
    }
    if extra:
        payload.update(extra)
    return payload


@pytest_asyncio.fixture
async def order_client(
    test_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[OrderTestClient]:
    from app.api.dependencies import CurrentUser, get_current_user
    from app.db.session import get_session
    from app.main import app
    from app.models import User
    from app.workers.celery_app import celery_app

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory.begin() as session:
        user = User(
            provider_sub="google|orders-test",
            email="orders-test@example.com",
            first_name="Ada",
            last_name="Obi",
            created_at=datetime.now(UTC),
        )
        session.add(user)
        await session.flush()
        user_id = user.id

    detached_user = User(
        id=user_id,
        provider_sub="google|orders-test",
        email="orders-test@example.com",
        first_name="Ada",
        last_name="Obi",
        created_at=datetime.now(UTC),
    )
    enqueued_tasks: list[tuple[str, list[int] | None]] = []

    def capture_task(task_name: str, args: list[int] | None = None, **_: Any) -> None:
        enqueued_tasks.append((task_name, args))

    monkeypatch.setattr(celery_app, "send_task", capture_task)

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    async def override_current_user() -> CurrentUser:
        return CurrentUser(user=detached_user)

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_user] = override_current_user
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            yield OrderTestClient(
                client,
                session_factory,
                user_id,
                detached_user,
                enqueued_tasks,
            )
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_current_user, None)
