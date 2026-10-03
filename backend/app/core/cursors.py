import base64
import json
from datetime import UTC, datetime
from typing import Any


class InvalidCursor(Exception):
    pass


def _encode(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _decode(cursor: str) -> dict[str, Any]:
    padding = "=" * (-len(cursor) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor + padding))
    except (ValueError, TypeError) as error:
        raise InvalidCursor from error
    if not isinstance(payload, dict):
        raise InvalidCursor
    return payload


def encode_created_cursor(created_at: datetime, row_id: int) -> str:
    return _encode({"created_at": created_at.timestamp(), "id": row_id})


def decode_created_cursor(cursor: str) -> tuple[datetime, int]:
    payload = _decode(cursor)
    timestamp = payload.get("created_at")
    row_id = payload.get("id")
    if isinstance(timestamp, bool) or isinstance(row_id, bool):
        raise InvalidCursor
    if not isinstance(timestamp, int | float) or not isinstance(row_id, int):
        raise InvalidCursor
    if row_id < 1:
        raise InvalidCursor
    return datetime.fromtimestamp(timestamp, tz=UTC), row_id
