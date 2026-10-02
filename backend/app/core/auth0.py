import asyncio
from collections.abc import Mapping
from time import monotonic
from typing import Any

import httpx
import jwt
from jwt import PyJWK

from app.core.config import settings


class InvalidAccessToken(Exception):
    pass


class AuthProviderUnavailable(Exception):
    pass


class Auth0TokenVerifier:
    def __init__(
        self,
        *,
        domain: str,
        audience: str,
        cache_ttl_seconds: int,
        timeout_seconds: int,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._issuer = f"https://{domain.rstrip('/')}/"
        self._jwks_url = f"{self._issuer}.well-known/jwks.json"
        self._audience = audience
        self._cache_ttl_seconds = cache_ttl_seconds
        self._timeout_seconds = timeout_seconds
        self._transport = transport
        self._keys: dict[str, Any] = {}
        self._expires_at = 0.0
        self._cache_lock = asyncio.Lock()

    async def verify(self, token: str) -> Mapping[str, Any]:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as error:
            raise InvalidAccessToken from error

        key_id = header.get("kid")
        if header.get("alg") != "RS256" or not isinstance(key_id, str):
            raise InvalidAccessToken

        public_key = await self._get_public_key(key_id)
        try:
            claims = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
        except jwt.PyJWTError as error:
            raise InvalidAccessToken from error
        return claims

    async def _get_public_key(self, key_id: str) -> Any:
        if monotonic() < self._expires_at and key_id in self._keys:
            return self._keys[key_id]

        async with self._cache_lock:
            if monotonic() >= self._expires_at or key_id not in self._keys:
                await self._refresh_keys()
            public_key = self._keys.get(key_id)
            if public_key is None:
                raise InvalidAccessToken
            return public_key

    async def _refresh_keys(self) -> None:
        try:
            async with httpx.AsyncClient(
                transport=self._transport,
                timeout=self._timeout_seconds,
            ) as client:
                response = await client.get(self._jwks_url)
                response.raise_for_status()
            document = response.json()
            raw_keys = document["keys"]
            keys = {
                item["kid"]: PyJWK.from_dict(item).key
                for item in raw_keys
                if isinstance(item, dict)
                and item.get("kty") == "RSA"
                and isinstance(item.get("kid"), str)
                and item.get("use", "sig") == "sig"
            }
        except (
            httpx.HTTPError,
            jwt.PyJWTError,
            KeyError,
            TypeError,
            ValueError,
        ) as error:
            raise AuthProviderUnavailable from error

        self._keys = keys
        self._expires_at = monotonic() + self._cache_ttl_seconds


token_verifier = Auth0TokenVerifier(
    domain=settings.auth0_domain,
    audience=settings.auth0_audience,
    cache_ttl_seconds=settings.jwks_cache_ttl_seconds,
    timeout_seconds=settings.jwks_timeout_seconds,
)
