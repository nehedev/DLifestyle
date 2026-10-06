import asyncio
from collections.abc import Mapping
from time import monotonic
from typing import Any

import httpx
import jwt
from jwt import PyJWK

from app.core.config import settings

_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
# Google's popup code flow has no redirect endpoint; the token exchange must
# present this literal value instead of a registered redirect URI.
_CODE_REDIRECT_URI = "postmessage"
_ALLOWED_ISSUERS = frozenset({"https://accounts.google.com", "accounts.google.com"})


class InvalidAccessToken(Exception):
    pass


class InvalidAuthorizationCode(Exception):
    pass


class AuthProviderUnavailable(Exception):
    pass


class GoogleTokenVerifier:
    def __init__(
        self,
        *,
        client_id: str,
        cache_ttl_seconds: int,
        timeout_seconds: int,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client_id = client_id
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
                audience=self._client_id,
                options={"require": ["exp", "aud", "sub", "iss"]},
            )
        except jwt.PyJWTError as error:
            raise InvalidAccessToken from error
        if claims.get("iss") not in _ALLOWED_ISSUERS:
            raise InvalidAccessToken
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
                response = await client.get(_JWKS_URL)
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


class GoogleCodeExchanger:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        timeout_seconds: int,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    async def exchange(self, code: str) -> str:
        payload = {
            "code": code,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "redirect_uri": _CODE_REDIRECT_URI,
            "grant_type": "authorization_code",
        }
        try:
            async with httpx.AsyncClient(
                transport=self._transport,
                timeout=self._timeout_seconds,
            ) as client:
                response = await client.post(_TOKEN_URL, data=payload)
        except httpx.HTTPError as error:
            raise AuthProviderUnavailable from error

        if response.status_code >= 500:
            raise AuthProviderUnavailable
        if response.status_code >= 400:
            raise InvalidAuthorizationCode

        try:
            document = response.json()
        except ValueError as error:
            raise AuthProviderUnavailable from error

        id_token = document.get("id_token")
        if not isinstance(id_token, str) or not id_token:
            raise InvalidAuthorizationCode
        return id_token


token_verifier = GoogleTokenVerifier(
    client_id=settings.google_client_id,
    cache_ttl_seconds=settings.jwks_cache_ttl_seconds,
    timeout_seconds=settings.jwks_timeout_seconds,
)

code_exchanger = GoogleCodeExchanger(
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret.get_secret_value(),
    timeout_seconds=settings.google_token_timeout_seconds,
)
