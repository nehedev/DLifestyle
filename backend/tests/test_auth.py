import asyncio
import base64
from collections.abc import AsyncIterator, Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import httpx
import jwt
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.api.dependencies import CurrentUser, get_owner_user
from app.core import auth0
from app.core.auth0 import Auth0TokenVerifier
from app.core.config import settings
from app.db.session import get_session
from app.main import app
from app.models import User
from app.services import users as users_service
from app.workers.celery_app import celery_app

_KEY_ID = "damis-auth-test-key"


def _base64url_integer(value: int) -> str:
    encoded = base64.urlsafe_b64encode(
        value.to_bytes((value.bit_length() + 7) // 8, "big")
    )
    return encoded.rstrip(b"=").decode("ascii")


@dataclass
class AuthTestClient:
    client: AsyncClient
    private_key: RSAPrivateKey
    jwks_requests: list[httpx.Request]
    jwks_status: list[int]
    enqueued_tasks: list[tuple[str, list[Any] | None]]

    def token(
        self,
        overrides: Mapping[str, Any] | None = None,
        *,
        remove_claims: tuple[str, ...] = (),
    ) -> str:
        now = datetime.now(UTC)
        claims: dict[str, Any] = {
            "iss": f"https://{settings.auth0_domain.rstrip('/')}/",
            "aud": settings.auth0_audience,
            "sub": "auth0|alice",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
            settings.auth0_email_claim: "alice@example.com",
            settings.auth0_first_name_claim: "Alice",
            settings.auth0_last_name_claim: "Lovelace",
            settings.auth0_roles_claim: [],
        }
        if overrides is not None:
            claims.update(overrides)
        for claim_name in remove_claims:
            claims.pop(claim_name, None)
        return jwt.encode(
            claims,
            self.private_key,
            algorithm="RS256",
            headers={"kid": _KEY_ID},
        )


@pytest.fixture(scope="module")
def private_key() -> RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest_asyncio.fixture
async def auth_client(
    test_engine: AsyncEngine,
    private_key: RSAPrivateKey,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[AuthTestClient]:
    public_numbers = private_key.public_key().public_numbers()
    jwks_document = {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": _KEY_ID,
                "n": _base64url_integer(public_numbers.n),
                "e": _base64url_integer(public_numbers.e),
            }
        ]
    }
    jwks_requests: list[httpx.Request] = []
    jwks_status = [200]
    enqueued_tasks: list[tuple[str, list[Any] | None]] = []

    def capture_task(
        task_name: str,
        args: list[Any] | None = None,
        **_: Any,
    ) -> None:
        enqueued_tasks.append((task_name, args))

    monkeypatch.setattr(celery_app, "send_task", capture_task)

    def handle_jwks(request: httpx.Request) -> httpx.Response:
        jwks_requests.append(request)
        return httpx.Response(jwks_status[0], json=jwks_document)

    verifier = Auth0TokenVerifier(
        domain=settings.auth0_domain,
        audience=settings.auth0_audience,
        cache_ttl_seconds=settings.jwks_cache_ttl_seconds,
        timeout_seconds=settings.jwks_timeout_seconds,
        transport=httpx.MockTransport(handle_jwks),
    )
    monkeypatch.setattr(auth0, "token_verifier", verifier)

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            yield AuthTestClient(
                client,
                private_key,
                jwks_requests,
                jwks_status,
                enqueued_tasks,
            )
    finally:
        app.dependency_overrides.pop(get_session, None)


async def _user_count(test_engine: AsyncEngine) -> int:
    async with test_engine.connect() as connection:
        count = await connection.scalar(select(func.count()).select_from(User))
    assert count is not None
    return count


async def _insert_user(
    test_engine: AsyncEngine,
    *,
    auth0_sub: str,
    email: str,
    first_name: str,
) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory.begin() as session:
        session.add(
            User(
                auth0_sub=auth0_sub,
                email=email,
                first_name=first_name,
                last_name=None,
                created_at=datetime.now(UTC),
            )
        )


async def test_me_provisions_and_syncs_user(
    auth_client: AuthTestClient,
    test_engine: AsyncEngine,
) -> None:
    first_response = await auth_client.client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {auth_client.token()}"},
    )
    assert first_response.status_code == 200
    first_profile = first_response.json()
    assert set(first_profile) == {
        "id",
        "email",
        "first_name",
        "last_name",
        "is_owner",
    }
    assert first_profile["is_owner"] is False
    assert first_profile["email"] == "alice@example.com"
    assert first_profile["first_name"] == "Alice"
    assert first_profile["last_name"] == "Lovelace"
    assert await _user_count(test_engine) == 1
    assert auth_client.enqueued_tasks == [("send_welcome_email", [first_profile["id"]])]

    changed_claims = {
        settings.auth0_email_claim: "updated@example.com",
        settings.auth0_first_name_claim: "Ada",
        settings.auth0_last_name_claim: "Byron",
    }
    second_response = await auth_client.client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {auth_client.token(changed_claims)}"},
    )
    assert second_response.status_code == 200
    assert second_response.json() == {
        "id": first_profile["id"],
        "email": "updated@example.com",
        "first_name": "Ada",
        "last_name": "Byron",
        "is_owner": False,
    }
    assert len(auth_client.jwks_requests) == 1
    assert len(auth_client.enqueued_tasks) == 1


@pytest.mark.parametrize(
    "missing_claim",
    [settings.auth0_email_claim, settings.auth0_first_name_claim],
)
async def test_required_profile_claims_are_rejected(
    auth_client: AuthTestClient,
    test_engine: AsyncEngine,
    missing_claim: str,
) -> None:
    response = await auth_client.client.get(
        "/api/v1/me",
        headers={
            "Authorization": f"Bearer "
            f"{auth_client.token(remove_claims=(missing_claim,))}"
        },
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid_token"}
    assert await _user_count(test_engine) == 0


@pytest.mark.parametrize("last_name", [None, "", "   "])
async def test_missing_or_empty_last_name_is_stored_as_null(
    auth_client: AuthTestClient,
    test_engine: AsyncEngine,
    last_name: str | None,
) -> None:
    overrides = {} if last_name is None else {settings.auth0_last_name_claim: last_name}
    remove_claims = (settings.auth0_last_name_claim,) if last_name is None else ()
    response = await auth_client.client.get(
        "/api/v1/me",
        headers={
            "Authorization": f"Bearer "
            f"{auth_client.token(overrides, remove_claims=remove_claims)}"
        },
    )
    assert response.status_code == 200
    assert response.json()["last_name"] is None

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        user = await session.scalar(select(User))
    assert user is not None
    assert user.last_name is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"iss": "https://attacker.example/"},
        {"aud": "wrong-audience"},
        {"exp": 0},
    ],
)
async def test_invalid_standard_jwt_claims_are_rejected(
    auth_client: AuthTestClient,
    overrides: Mapping[str, Any],
) -> None:
    response = await auth_client.client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {auth_client.token(overrides)}"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid_token"}


async def test_tampered_rs256_signature_is_rejected(
    auth_client: AuthTestClient,
) -> None:
    token_parts = auth_client.token().split(".")
    signature = token_parts[2]
    replacement = "A" if signature[0] != "A" else "B"
    token_parts[2] = replacement + signature[1:]
    response = await auth_client.client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {'.'.join(token_parts)}"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid_token"}


async def test_missing_exp_claim_is_rejected(
    auth_client: AuthTestClient,
) -> None:
    token = auth_client.token(remove_claims=("exp",))
    response = await auth_client.client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid_token"}


async def test_missing_bearer_token_is_rejected() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/v1/me")
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid_token"}


async def test_jwks_failure_returns_service_unavailable(
    auth_client: AuthTestClient,
) -> None:
    auth_client.jwks_status[0] = 503
    response = await auth_client.client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {auth_client.token()}"},
    )
    assert response.status_code == 503
    assert response.json() == {"detail": "auth_provider_unavailable"}


async def test_email_conflict_on_first_provisioning_writes_nothing(
    auth_client: AuthTestClient,
    test_engine: AsyncEngine,
) -> None:
    await _insert_user(
        test_engine,
        auth0_sub="auth0|original",
        email="alice@example.com",
        first_name="Original",
    )
    response = await auth_client.client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {auth_client.token()}"},
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "account_exists_use_existing_sign_in"}
    assert await _user_count(test_engine) == 1


async def test_email_conflict_during_sync_writes_nothing(
    auth_client: AuthTestClient,
    test_engine: AsyncEngine,
) -> None:
    await _insert_user(
        test_engine,
        auth0_sub="auth0|alice",
        email="alice@example.com",
        first_name="Alice",
    )
    await _insert_user(
        test_engine,
        auth0_sub="auth0|other",
        email="other@example.com",
        first_name="Other",
    )
    conflicting_token = auth_client.token(
        {settings.auth0_email_claim: "other@example.com"}
    )
    response = await auth_client.client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {conflicting_token}"},
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "account_exists_use_existing_sign_in"}

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        alice = await session.scalar(
            select(User).where(User.auth0_sub == "auth0|alice")
        )
    assert alice is not None
    assert alice.email == "alice@example.com"
    assert alice.first_name == "Alice"
    assert await _user_count(test_engine) == 2


async def test_concurrent_first_requests_create_one_user(
    auth_client: AuthTestClient,
    test_engine: AsyncEngine,
) -> None:
    token = auth_client.token()
    responses: list[httpx.Response] = []

    async def request_profile() -> None:
        response = await auth_client.client.get(
            "/api/v1/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        responses.append(response)

    async with asyncio.TaskGroup() as task_group:
        task_group.create_task(request_profile())
        task_group.create_task(request_profile())

    assert len(responses) == 2
    assert all(response.status_code == 200 for response in responses)
    assert responses[0].json()["id"] == responses[1].json()["id"]
    assert await _user_count(test_engine) == 1
    assert len(auth_client.jwks_requests) == 1
    assert auth_client.enqueued_tasks == [
        ("send_welcome_email", [responses[0].json()["id"]])
    ]


async def test_the_email_conflict_is_decided_after_the_insert_is_attempted(
    test_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The insert must be attempted before the email conflict is decided.

    Checking email availability first is a race. A concurrent request can
    commit its own newly created row between that check and the insert, so
    the loser of the insert race would then report a conflict against the
    very row it was racing to create, and the pair would answer 200 and 409
    instead of 200 and 200.
    """
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory.begin() as session:
        session.add(
            User(
                auth0_sub="auth0|existing",
                email="shared@example.com",
                first_name="Existing",
                last_name=None,
                created_at=datetime.now(UTC),
            )
        )

    claims = {
        "sub": "auth0|newcomer",
        settings.auth0_email_claim: "shared@example.com",
        settings.auth0_first_name_claim: "New",
        settings.auth0_last_name_claim: "Comer",
    }
    order: list[str] = []
    original_check = users_service._ensure_email_available
    original_insert = users_service.pg_insert

    async def recording_check(
        session: AsyncSession,
        email: str,
        *,
        exclude_user_id: int | None = None,
    ) -> None:
        order.append("check")
        await original_check(session, email, exclude_user_id=exclude_user_id)

    def recording_insert(*args: Any, **kwargs: Any):
        order.append("insert")
        return original_insert(*args, **kwargs)

    monkeypatch.setattr(users_service, "_ensure_email_available", recording_check)
    monkeypatch.setattr(users_service, "pg_insert", recording_insert)

    async with session_factory() as session:
        with pytest.raises(users_service.EmailConflict):
            await users_service.resolve_current_user(session, claims)

    assert order == ["insert", "check"]


@pytest.mark.parametrize(
    ("roles_claim", "expected_is_owner"),
    [
        (["owner"], True),
        (["customer", "owner"], True),
        (["customer"], False),
        ([], False),
    ],
)
async def test_roles_claim_decides_is_owner(
    auth_client: AuthTestClient,
    roles_claim: list[str] | None,
    expected_is_owner: bool,
) -> None:
    overrides = {} if roles_claim is None else {settings.auth0_roles_claim: roles_claim}
    remove_claims = () if roles_claim is not None else (settings.auth0_roles_claim,)
    response = await auth_client.client.get(
        "/api/v1/me",
        headers={
            "Authorization": f"Bearer "
            f"{auth_client.token(overrides, remove_claims=remove_claims)}"
        },
    )
    assert response.status_code == 200
    assert response.json()["is_owner"] is expected_is_owner


@pytest.mark.parametrize(
    "roles_claim",
    ["owner", None, 42, {"name": "owner"}],
)
async def test_a_malformed_roles_claim_grants_no_roles(
    auth_client: AuthTestClient,
    roles_claim: Any,
) -> None:
    response = await auth_client.client.get(
        "/api/v1/me",
        headers={
            "Authorization": f"Bearer "
            f"{auth_client.token({settings.auth0_roles_claim: roles_claim})}"
        },
    )
    assert response.status_code == 200
    assert response.json()["is_owner"] is False


@pytest.fixture
def owner_probe_app(test_engine: AsyncEngine) -> Iterator[FastAPI]:
    """A throwaway app whose single route stands in for an admin endpoint.

    Admin routes arrive in a later milestone. This proves the OwnerUser
    dependency itself: no token is 401, a valid token without the owner
    role is 403, and only the owner role passes.
    """
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    probe = FastAPI()

    @probe.get("/probe", response_model=dict[str, bool])
    async def read_probe(
        current_user: Annotated[CurrentUser, Depends(get_owner_user)],
    ) -> dict[str, bool]:
        return {"is_owner": current_user.is_owner}

    probe.dependency_overrides[get_session] = override_get_session
    yield probe
    probe.dependency_overrides.clear()


async def _probe(
    owner_probe_app: FastAPI,
    token: str | None,
) -> httpx.Response:
    async with AsyncClient(
        transport=ASGITransport(app=owner_probe_app),
        base_url="http://testserver",
    ) as client:
        return await client.get(
            "/probe",
            headers={} if token is None else {"Authorization": f"Bearer {token}"},
        )


async def test_owner_route_without_a_token_is_401(
    owner_probe_app: FastAPI,
) -> None:
    response = await _probe(owner_probe_app, None)
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid_token"}


async def test_owner_route_with_a_valid_token_without_the_role_is_403(
    owner_probe_app: FastAPI,
    auth_client: AuthTestClient,
) -> None:
    response = await _probe(owner_probe_app, auth_client.token())
    assert response.status_code == 403
    assert response.json() == {"detail": "owner_required"}


async def test_owner_route_with_an_invalid_token_is_401_not_403(
    owner_probe_app: FastAPI,
    auth_client: AuthTestClient,
) -> None:
    response = await _probe(owner_probe_app, "not-a-jwt")
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid_token"}


async def test_owner_route_with_the_owner_role_passes(
    owner_probe_app: FastAPI,
    auth_client: AuthTestClient,
) -> None:
    response = await _probe(
        owner_probe_app,
        auth_client.token({settings.auth0_roles_claim: ["owner"]}),
    )
    assert response.status_code == 200
    assert response.json() == {"is_owner": True}
