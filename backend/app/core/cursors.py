import base64
import binascii
import json
from datetime import datetime
from typing import Any


class InvalidCursor(ValueError):
    pass


def _encode(payload: dict[str, int | str]) -> str:
    serialized = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(serialized).rstrip(b"=").decode("ascii")


def _decode(cursor: str) -> dict[str, Any]:
    try:
        padding = "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(cursor + padding).decode("utf-8"))
    except (
        binascii.Error,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
    ) as error:
        raise InvalidCursor from error
    if not isinstance(payload, dict):
        raise InvalidCursor
    return payload


def encode_product_cursor(product_id: int) -> str:
    return _encode({"id": product_id})


def decode_product_cursor(cursor: str) -> int:
    payload = _decode(cursor)
    product_id = payload.get("id")
    if (
        isinstance(product_id, bool)
        or not isinstance(product_id, int)
        or product_id < 1
    ):
        raise InvalidCursor
    return product_id


def encode_order_cursor(created_at: datetime, order_id: int) -> str:
    return _encode({"created_at": created_at.isoformat(), "id": order_id})


def decode_order_cursor(cursor: str) -> tuple[datetime, int]:
    payload = _decode(cursor)
    raw_created_at = payload.get("created_at")
    order_id = payload.get("id")
    if (
        not isinstance(raw_created_at, str)
        or isinstance(order_id, bool)
        or not isinstance(order_id, int)
        or order_id < 1
    ):
        raise InvalidCursor
    try:
        created_at = datetime.fromisoformat(raw_created_at)
    except ValueError as error:
        raise InvalidCursor from error
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise InvalidCursor
    return created_at, order_id
