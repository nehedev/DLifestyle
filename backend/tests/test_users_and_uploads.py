"""Tests for user listing, role management, and the Cloudinary upload-sign endpoint."""

import hashlib
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.api.dependencies import CurrentUser, get_current_user
from app.core.config import settings
from app.db.session import get_session
from app.main import app
from app.models import User


def _now() -> datetime:
    return datetime.now(UTC)


@pytest_asyncio.fixture
async def session_factory(
    test_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, expire_on_commit=False)


async def _add_user(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    sub: str,
    email: str,
    first_name: str = "Test",
    role: str = "user",
) -> tuple[int, User]:
    async with session_factory.begin() as session:
        user = User(
            provider_sub=sub,
            email=email,
            first_name=first_name,
            last_name=None,
            created_at=_now(),
        )
        # role has a server_default, so we set it explicitly on the ORM object
        user.role = role
        session.add(user)
        await session.flush()
        uid = user.id
    detached = User(
        id=uid,
        provider_sub=sub,
        email=email,
        first_name=first_name,
        last_name=None,
        created_at=_now(),
    )
    detached.role = role
    return uid, detached


def _session_override(sf: async_sessionmaker[AsyncSession]):
    async def override() -> AsyncIterator[AsyncSession]:
        async with sf() as session:
            yield session

    return override


def _user_override(user: User):
    async def override() -> CurrentUser:
        return CurrentUser(user=user)

    return override


def _client() -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    )


@pytest_asyncio.fixture
async def admin_client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    _, admin = await _add_user(
        session_factory,
        sub="google|admin-users-test",
        email="admin-users@example.com",
        role="admin",
    )
    app.dependency_overrides[get_session] = _session_override(session_factory)
    app.dependency_overrides[get_current_user] = _user_override(admin)
    try:
        async with _client() as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest_asyncio.fixture
async def customer_client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    _, customer = await _add_user(
        session_factory,
        sub="google|customer-users-test",
        email="customer-users@example.com",
        role="user",
    )
    app.dependency_overrides[get_session] = _session_override(session_factory)
    app.dependency_overrides[get_current_user] = _user_override(customer)
    try:
        async with _client() as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest_asyncio.fixture
async def anonymous_client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    app.dependency_overrides[get_session] = _session_override(session_factory)
    # no current_user override → bearer scheme returns 401
    try:
        async with _client() as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# GET /sudo/users
# ---------------------------------------------------------------------------


async def test_list_users_without_token_is_401(
    anonymous_client: AsyncClient,
) -> None:
    response = await anonymous_client.get("/api/v1/sudo/users")
    assert response.status_code == 401


async def test_list_users_as_customer_is_403(
    customer_client: AsyncClient,
) -> None:
    response = await customer_client.get("/api/v1/sudo/users")
    assert response.status_code == 403
    assert response.json() == {"detail": "admin_required"}


async def test_list_users_returns_all_users_with_correct_shape(
    admin_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    uid, _ = await _add_user(
        session_factory,
        sub="google|extra-user",
        email="extra@example.com",
        first_name="Extra",
    )

    response = await admin_client.get("/api/v1/sudo/users")

    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert "next_cursor" in body
    # At least two users: the admin fixture user + the extra one we just added
    assert len(body["items"]) >= 2
    extra = next(item for item in body["items"] if item["id"] == uid)
    assert extra["email"] == "extra@example.com"
    assert extra["first_name"] == "Extra"
    assert extra["role"] == "user"
    assert set(extra) == {
        "id",
        "email",
        "first_name",
        "last_name",
        "role",
        "created_at",
    }


async def test_list_users_paginates_correctly(
    admin_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # Add enough users to span two pages
    for i in range(3):
        await _add_user(
            session_factory,
            sub=f"google|page-user-{i}",
            email=f"page{i}@example.com",
        )

    page_one = await admin_client.get("/api/v1/sudo/users?limit=2")
    assert page_one.status_code == 200
    assert len(page_one.json()["items"]) == 2
    cursor = page_one.json()["next_cursor"]
    assert cursor is not None

    page_two = await admin_client.get(
        "/api/v1/sudo/users", params={"cursor": cursor, "limit": 2}
    )
    assert page_two.status_code == 200
    ids_p1 = {item["id"] for item in page_one.json()["items"]}
    ids_p2 = {item["id"] for item in page_two.json()["items"]}
    assert ids_p1.isdisjoint(ids_p2), "Pages must not overlap"


async def test_list_users_rejects_invalid_cursor(
    admin_client: AsyncClient,
) -> None:
    response = await admin_client.get(
        "/api/v1/sudo/users", params={"cursor": "not-a-cursor"}
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "invalid_cursor"}


# ---------------------------------------------------------------------------
# PATCH /sudo/users/{id}/role
# ---------------------------------------------------------------------------


async def test_patch_role_without_token_is_401(
    anonymous_client: AsyncClient,
) -> None:
    response = await anonymous_client.patch(
        "/api/v1/sudo/users/1/role", json={"role": "admin"}
    )
    assert response.status_code == 401


async def test_patch_role_as_customer_is_403(
    customer_client: AsyncClient,
) -> None:
    response = await customer_client.patch(
        "/api/v1/sudo/users/1/role", json={"role": "admin"}
    )
    assert response.status_code == 403


async def test_admin_grants_admin_role(
    admin_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    uid, _ = await _add_user(
        session_factory,
        sub="google|promote-me",
        email="promote@example.com",
        role="user",
    )

    response = await admin_client.patch(
        f"/api/v1/sudo/users/{uid}/role", json={"role": "admin"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == uid
    assert body["role"] == "admin"

    async with session_factory() as session:
        user = await session.get(User, uid)
    assert user is not None
    assert user.role == "admin"


async def test_admin_revokes_admin_role(
    admin_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    uid, _ = await _add_user(
        session_factory,
        sub="google|demote-me",
        email="demote@example.com",
        role="admin",
    )

    response = await admin_client.patch(
        f"/api/v1/sudo/users/{uid}/role", json={"role": "user"}
    )

    assert response.status_code == 200
    assert response.json()["role"] == "user"

    async with session_factory() as session:
        user = await session.get(User, uid)
    assert user is not None
    assert user.role == "user"


async def test_admin_can_change_their_own_role(
    admin_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # The admin fixture user is "admin-users@example.com"
    async with session_factory() as session:
        from sqlalchemy import select

        admin_user = await session.scalar(
            select(User).where(User.email == "admin-users@example.com")
        )
    assert admin_user is not None

    response = await admin_client.patch(
        f"/api/v1/sudo/users/{admin_user.id}/role", json={"role": "user"}
    )
    assert response.status_code == 200
    assert response.json()["role"] == "user"


async def test_patch_role_of_missing_user_is_404(
    admin_client: AsyncClient,
) -> None:
    response = await admin_client.patch(
        "/api/v1/sudo/users/999999/role", json={"role": "admin"}
    )
    assert response.status_code == 404


@pytest.mark.parametrize("role", ["owner", "superuser", "", "ADMIN"])
async def test_patch_role_rejects_invalid_roles(
    admin_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    role: str,
) -> None:
    uid, _ = await _add_user(
        session_factory,
        sub=f"google|invalid-role-{role}",
        email=f"invalid-role-{role}@example.com",
    )
    response = await admin_client.patch(
        f"/api/v1/sudo/users/{uid}/role", json={"role": role}
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /sudo/uploads/sign
# ---------------------------------------------------------------------------


async def test_uploads_sign_without_token_is_401(
    anonymous_client: AsyncClient,
) -> None:
    response = await anonymous_client.post("/api/v1/sudo/uploads/sign")
    assert response.status_code == 401


async def test_uploads_sign_as_customer_is_403(
    customer_client: AsyncClient,
) -> None:
    response = await customer_client.post("/api/v1/sudo/uploads/sign")
    assert response.status_code == 403


async def test_uploads_sign_returns_correct_shape(
    admin_client: AsyncClient,
) -> None:
    response = await admin_client.post("/api/v1/sudo/uploads/sign")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "cloud_name",
        "api_key",
        "timestamp",
        "folder",
        "upload_url",
        "signature",
    }


async def test_uploads_sign_returns_configured_values(
    admin_client: AsyncClient,
) -> None:
    response = await admin_client.post("/api/v1/sudo/uploads/sign")
    body = response.json()

    assert body["cloud_name"] == settings.cloudinary_cloud_name
    assert body["api_key"] == settings.cloudinary_api_key
    assert body["folder"] == settings.cloudinary_upload_folder
    assert body["upload_url"] == (
        f"https://api.cloudinary.com/v1_1/{settings.cloudinary_cloud_name}/image/upload"
    )


async def test_uploads_sign_signature_validates_against_configured_secret(
    admin_client: AsyncClient,
) -> None:
    before = int(time.time())
    response = await admin_client.post("/api/v1/sudo/uploads/sign")
    after = int(time.time())

    assert response.status_code == 200
    body = response.json()

    # timestamp must be current
    assert before <= body["timestamp"] <= after

    # recompute the signature the same way the service does
    folder = body["folder"]
    timestamp = body["timestamp"]
    secret = settings.cloudinary_api_secret.get_secret_value()
    to_sign = f"folder={folder}&timestamp={timestamp}{secret}"
    expected = hashlib.sha1(to_sign.encode()).hexdigest()  # noqa: S324

    assert body["signature"] == expected


async def test_uploads_sign_api_secret_is_not_in_response(
    admin_client: AsyncClient,
) -> None:
    response = await admin_client.post("/api/v1/sudo/uploads/sign")
    body_text = response.text
    secret = settings.cloudinary_api_secret.get_secret_value()

    assert secret not in body_text
