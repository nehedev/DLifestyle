import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection as SyncConnection
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

_TEST_SETTINGS = {
    "DATABASE_URL": "postgresql+asyncpg://ficmart:ficmart@localhost:5432/ficmart",
    "REDIS_URL": "redis://localhost:6379/0",
    "AUTH0_DOMAIN": "tenant.example.com",
    "AUTH0_AUDIENCE": "https://api.ficmart.example.com",
    "AUTH0_EMAIL_CLAIM": "https://ficmart.example.com/email",
    "AUTH0_FIRST_NAME_CLAIM": "https://ficmart.example.com/first_name",
    "AUTH0_LAST_NAME_CLAIM": "https://ficmart.example.com/last_name",
    "AUTH0_ROLES_CLAIM": "https://ficmart.example.com/roles",
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
    "PENDING_ORDER_TIMEOUT_MINUTES": "15",
    "EXPIRY_JOB_INTERVAL_MINUTES": "5",
    "CELERY_TASK_MAX_RETRIES": "5",
    "CELERY_RETRY_BACKOFF_MAX_SECONDS": "600",
}
for variable, value in _TEST_SETTINGS.items():
    os.environ.setdefault(variable, value)


def pytest_configure() -> None:
    for variable, value in _TEST_SETTINGS.items():
        os.environ.setdefault(variable, value)


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
