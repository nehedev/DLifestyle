from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from conftest import OrderTestClient

from app.core.config import settings
from app.models import StoreSettings
from app.services.store_settings import cutoff_instant, is_ordering_open

BUSINESS_ZONE = ZoneInfo(settings.business_timezone)
LAGOS_OFFSET = timedelta(hours=1)


def business_now() -> datetime:
    return datetime.now(UTC).astimezone(BUSINESS_ZONE)


def _store_settings(
    *,
    cutoff: time = time(16, 0),
    max_advance_days: int = 7,
) -> StoreSettings:
    return StoreSettings(
        id=1,
        delivery_fee_minor=0,
        order_cutoff_time=cutoff,
        max_advance_days=max_advance_days,
        updated_at=datetime.now(UTC),
    )


@pytest.mark.parametrize(
    ("lagos_now", "fulfillment_date", "expected"),
    [
        # Same-day before the cutoff is open.
        ("2026-10-03T09:00", "2026-10-03", True),
        # Same-day at the cutoff instant is closed: the rule is "before".
        ("2026-10-03T16:00", "2026-10-03", False),
        ("2026-10-03T15:59", "2026-10-03", True),
        ("2026-10-03T16:01", "2026-10-03", False),
        # Yesterday and earlier are always closed.
        ("2026-10-03T09:00", "2026-10-02", False),
        ("2026-10-03T09:00", "2026-09-01", False),
        # max_advance_days is inclusive.
        ("2026-10-03T09:00", "2026-10-10", True),
        ("2026-10-03T09:00", "2026-10-11", False),
    ],
)
def test_date_rules_in_the_business_timezone(
    lagos_now: str,
    fulfillment_date: str,
    expected: bool,
) -> None:
    now = datetime.fromisoformat(lagos_now).replace(tzinfo=BUSINESS_ZONE)
    opened = is_ordering_open(
        _store_settings(max_advance_days=7),
        fulfillment_date=date.fromisoformat(fulfillment_date),
        now=now,
    )
    assert opened is expected


def test_a_zero_advance_window_only_allows_today() -> None:
    now = datetime(2026, 10, 3, 9, 0, tzinfo=BUSINESS_ZONE)
    store_settings = _store_settings(max_advance_days=0)
    assert is_ordering_open(store_settings, fulfillment_date=date(2026, 10, 3), now=now)
    assert not is_ordering_open(
        store_settings, fulfillment_date=date(2026, 10, 4), now=now
    )


def test_a_past_cutoff_time_closes_today_but_not_tomorrow() -> None:
    now = datetime(2026, 10, 3, 22, 0, tzinfo=BUSINESS_ZONE)
    store_settings = _store_settings(cutoff=time(21, 0))
    assert not is_ordering_open(
        store_settings, fulfillment_date=date(2026, 10, 3), now=now
    )
    assert is_ordering_open(store_settings, fulfillment_date=date(2026, 10, 4), now=now)


def test_the_business_date_can_differ_from_the_utc_date() -> None:
    """23:30 UTC is already the next calendar day in Africa/Lagos."""
    utc_now = datetime(2026, 10, 3, 23, 30, tzinfo=UTC)
    assert utc_now.astimezone(BUSINESS_ZONE).date() == date(2026, 10, 4)

    store_settings = _store_settings(cutoff=time(23, 0))
    assert not is_ordering_open(
        store_settings, fulfillment_date=date(2026, 10, 3), now=utc_now
    )
    assert is_ordering_open(
        store_settings, fulfillment_date=date(2026, 10, 4), now=utc_now
    )


def test_the_cutoff_instant_is_read_in_the_business_timezone() -> None:
    cutoff = cutoff_instant(
        _store_settings(cutoff=time(16, 0)),
        fulfillment_date=date(2026, 10, 4),
    )
    assert cutoff == datetime(2026, 10, 4, 16, 0, tzinfo=BUSINESS_ZONE)
    assert cutoff.utcoffset() == LAGOS_OFFSET
    assert cutoff.astimezone(UTC) == datetime(2026, 10, 4, 15, 0, tzinfo=UTC)


async def test_a_past_date_is_rejected(
    order_client: OrderTestClient,
) -> None:
    await order_client.configure_store()
    menu_item_id = await order_client.add_menu_item(weekdays=(1, 2, 3, 4, 5, 6, 7))
    response = await order_client.client.post(
        "/api/v1/orders",
        json=_payload(menu_item_id, business_now().date() - timedelta(days=1)),
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "ordering_closed_for_date"}


async def test_a_date_beyond_max_advance_days_is_rejected(
    order_client: OrderTestClient,
) -> None:
    await order_client.configure_store(max_advance_days=3)
    menu_item_id = await order_client.add_menu_item(weekdays=(1, 2, 3, 4, 5, 6, 7))
    today = business_now().date()

    inside = await order_client.client.post(
        "/api/v1/orders", json=_payload(menu_item_id, today + timedelta(days=3))
    )
    beyond = await order_client.client.post(
        "/api/v1/orders", json=_payload(menu_item_id, today + timedelta(days=4))
    )

    assert inside.status_code == 200
    assert beyond.status_code == 409
    assert beyond.json() == {"detail": "ordering_closed_for_date"}


async def test_a_date_after_the_cutoff_is_rejected(
    order_client: OrderTestClient,
) -> None:
    menu_item_id = await order_client.add_menu_item(weekdays=(1, 2, 3, 4, 5, 6, 7))
    now = business_now()
    earlier = now - timedelta(hours=1)
    # Near midnight "now - 1h" falls on the previous day, so its time is not
    # actually in the past for today. Midnight is always a passed cutoff.
    cutoff_already_passed = (
        time(0, 0) if earlier.date() != now.date() else earlier.time()
    )
    await order_client.configure_store(cutoff=cutoff_already_passed)

    today = await order_client.client.post(
        "/api/v1/orders", json=_payload(menu_item_id, now.date())
    )
    tomorrow = await order_client.client.post(
        "/api/v1/orders", json=_payload(menu_item_id, now.date() + timedelta(days=1))
    )

    assert today.status_code == 409
    assert today.json() == {"detail": "ordering_closed_for_date"}
    assert tomorrow.status_code == 200


async def test_same_day_before_the_cutoff_succeeds(
    order_client: OrderTestClient,
) -> None:
    menu_item_id = await order_client.add_menu_item(weekdays=(1, 2, 3, 4, 5, 6, 7))
    now = business_now()
    ahead = now + timedelta(hours=1)
    # Near midnight the +1h cutoff would roll into the next day and close
    # today. Fall back to the last instant of the current day, which is
    # still ahead of "now" and keeps the same-day case deterministic.
    cutoff_still_ahead = (
        time(23, 59, 59, 999999) if ahead.date() != now.date() else ahead.time()
    )
    await order_client.configure_store(cutoff=cutoff_still_ahead)

    response = await order_client.client.post(
        "/api/v1/orders", json=_payload(menu_item_id, now.date())
    )

    assert response.status_code == 200
    assert response.json()["fulfillment_date"] == now.date().isoformat()


async def test_the_date_rules_apply_before_the_item_rules(
    order_client: OrderTestClient,
) -> None:
    """A closed date wins over an unavailable item."""
    await order_client.configure_store(max_advance_days=1)
    menu_item_id = await order_client.add_menu_item(is_active=False)
    today = business_now().date()

    response = await order_client.client.post(
        "/api/v1/orders", json=_payload(menu_item_id, today + timedelta(days=9))
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "ordering_closed_for_date"}


def _payload(menu_item_id: int, fulfillment_date: date) -> dict[str, object]:
    return {
        "items": [{"menu_item_id": menu_item_id, "quantity": 1}],
        "fulfillment_type": "delivery",
        "fulfillment_date": fulfillment_date.isoformat(),
        "contact": {
            "name": "Ada Obi",
            "phone": "+2348012345678",
            "address": "12 Example Street, Lekki",
        },
        "notes": None,
    }
