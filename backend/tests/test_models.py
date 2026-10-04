from datetime import UTC, date, datetime, time

import pytest
from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.base import Base
from app.models import (
    MenuItem,
    MenuItemDay,
    Order,
    OrderItem,
    Payment,
    Service,
    ServiceRequest,
    StoreSettings,
    User,
)


def _now() -> datetime:
    return datetime.now(UTC)


async def _insert_user(connection, *, sub: str, email: str) -> int:
    result = await connection.execute(
        insert(User).values(
            provider_sub=sub,
            email=email,
            first_name="Constraint",
            created_at=_now(),
        )
    )
    assert result.inserted_primary_key is not None
    return int(result.inserted_primary_key[0])


async def _insert_menu_item(connection, **overrides: object) -> int:
    values: dict[str, object] = {
        "name": "Constraint item",
        "category": "Rice",
        "price_minor": 100,
        "is_active": True,
        "is_sold_out": False,
        "created_at": _now(),
        "updated_at": _now(),
    }
    values.update(overrides)
    result = await connection.execute(insert(MenuItem).values(**values))
    assert result.inserted_primary_key is not None
    return int(result.inserted_primary_key[0])


async def _insert_order(connection, **overrides: object) -> int:
    values: dict[str, object] = {
        "user_id": 1,
        "status": "pending",
        "fulfillment_type": "delivery",
        "fulfillment_date": date(2026, 10, 5),
        "contact": {"name": "Ada", "phone": "+2348012345678", "address": "Lekki"},
        "items_total_minor": 100,
        "delivery_fee_minor": 0,
        "total_minor": 100,
        "currency": "NGN",
        "created_at": _now(),
        "updated_at": _now(),
    }
    values.update(overrides)
    result = await connection.execute(insert(Order).values(**values))
    assert result.inserted_primary_key is not None
    return int(result.inserted_primary_key[0])


def test_metadata_has_exactly_the_specified_tables() -> None:
    assert set(Base.metadata.tables) == {
        "users",
        "menu_items",
        "menu_item_days",
        "services",
        "store_settings",
        "orders",
        "order_items",
        "payments",
        "service_requests",
    }


@pytest.mark.parametrize(
    ("table", "expected_constraints"),
    [
        (
            "menu_items",
            {"ck_menu_items_price_minor_nonnegative"},
        ),
        (
            "menu_item_days",
            {"ck_menu_item_days_weekday_iso_range", "pk_menu_item_days"},
        ),
        (
            "store_settings",
            {
                "ck_store_settings_singleton_row",
                "ck_store_settings_delivery_fee_minor_nonnegative",
                "ck_store_settings_max_advance_days_nonnegative",
            },
        ),
        (
            "orders",
            {
                "ck_orders_valid_status",
                "ck_orders_valid_fulfillment_type",
                "ck_orders_items_total_nonnegative",
                "ck_orders_delivery_fee_nonnegative",
                "ck_orders_total_nonnegative",
                "uq_orders_user_id_idempotency_key",
                "ix_orders_user_id",
            },
        ),
        (
            "order_items",
            {
                "ck_order_items_quantity_positive",
                "ck_order_items_unit_price_minor_nonnegative",
                "uq_order_items_order_item",
            },
        ),
        (
            "payments",
            {
                "ck_payments_valid_status",
                "ck_payments_amount_minor_nonnegative",
                "uq_payments_reference",
                "uq_payments_provider_transaction",
                "ix_payments_order_id",
            },
        ),
        (
            "service_requests",
            {
                "ck_service_requests_valid_status",
                "ck_service_requests_quoted_amount_minor_nonnegative",
                "ix_service_requests_user_id",
                "ix_service_requests_status",
            },
        ),
        ("users", {"uq_users_provider_sub", "uq_users_email", "ck_users_valid_role"}),
    ],
)
def test_named_constraints_and_indexes_exist(
    table: str,
    expected_constraints: set[str],
) -> None:
    declared = Base.metadata.tables[table]
    names = {constraint.name for constraint in declared.constraints}
    names |= {index.name for index in declared.indexes}
    assert expected_constraints <= names


def test_store_settings_primary_key_is_the_singleton_column() -> None:
    table = Base.metadata.tables["store_settings"]
    assert [column.name for column in table.primary_key.columns] == ["id"]


def test_menu_item_days_primary_key_is_menu_item_and_weekday() -> None:
    table = Base.metadata.tables["menu_item_days"]
    assert [column.name for column in table.primary_key.columns] == [
        "menu_item_id",
        "weekday",
    ]


async def test_check_constraints_reject_invalid_values(
    test_engine: AsyncEngine,
) -> None:
    async def assert_rejected(connection, statement) -> None:
        with pytest.raises(IntegrityError):
            async with connection.begin_nested():
                await connection.execute(statement)

    async with test_engine.connect() as connection:
        async with connection.begin():
            user_id = await _insert_user(
                connection, sub="google|checks", email="checks@example.com"
            )
            menu_item_id = await _insert_menu_item(connection)
            order_id = await _insert_order(connection, user_id=user_id)

            await assert_rejected(
                connection,
                insert(MenuItem).values(
                    name="Negative price",
                    category="Rice",
                    price_minor=-1,
                    is_active=True,
                    is_sold_out=False,
                    created_at=_now(),
                    updated_at=_now(),
                ),
            )
            for weekday in (0, 8, -1):
                await assert_rejected(
                    connection,
                    insert(MenuItemDay).values(
                        menu_item_id=menu_item_id, weekday=weekday
                    ),
                )
            for status in ("shipped", "refunded", "unknown"):
                await assert_rejected(
                    connection,
                    update(Order).where(Order.id == order_id).values(status=status),
                )
            await assert_rejected(
                connection,
                update(Order)
                .where(Order.id == order_id)
                .values(fulfillment_type="courier"),
            )
            await assert_rejected(
                connection,
                update(Order).where(Order.id == order_id).values(total_minor=-1),
            )
            await assert_rejected(
                connection,
                insert(OrderItem).values(
                    order_id=order_id,
                    menu_item_id=menu_item_id,
                    name="Constraint",
                    quantity=0,
                    unit_price_minor=100,
                ),
            )
            await assert_rejected(
                connection,
                insert(Payment).values(
                    order_id=order_id,
                    provider="paystack",
                    reference="invalid-status-reference",
                    amount_minor=100,
                    currency="NGN",
                    status="unknown",
                    created_at=_now(),
                    updated_at=_now(),
                ),
            )
            await assert_rejected(
                connection,
                insert(Payment).values(
                    order_id=order_id,
                    provider="paystack",
                    reference="negative-amount-reference",
                    amount_minor=-1,
                    currency="NGN",
                    status="initiated",
                    created_at=_now(),
                    updated_at=_now(),
                ),
            )


async def test_store_settings_is_a_single_row(test_engine: AsyncEngine) -> None:
    async with test_engine.connect() as connection:
        async with connection.begin():
            await connection.execute(
                insert(StoreSettings).values(
                    id=1,
                    delivery_fee_minor=1500,
                    order_cutoff_time=time(16, 0),
                    max_advance_days=7,
                    updated_at=_now(),
                )
            )
            for invalid_id in (0, 2):
                with pytest.raises(IntegrityError):
                    async with connection.begin_nested():
                        await connection.execute(
                            insert(StoreSettings).values(
                                id=invalid_id,
                                delivery_fee_minor=0,
                                order_cutoff_time=time(16, 0),
                                max_advance_days=7,
                                updated_at=_now(),
                            )
                        )
            with pytest.raises(IntegrityError):
                async with connection.begin_nested():
                    await connection.execute(
                        update(StoreSettings)
                        .where(StoreSettings.id == 1)
                        .values(delivery_fee_minor=-1)
                    )
            with pytest.raises(IntegrityError):
                async with connection.begin_nested():
                    await connection.execute(
                        update(StoreSettings)
                        .where(StoreSettings.id == 1)
                        .values(max_advance_days=-1)
                    )


async def test_unique_constraints_are_enforced(test_engine: AsyncEngine) -> None:
    async def assert_rejected(connection, statement) -> None:
        with pytest.raises(IntegrityError):
            async with connection.begin_nested():
                await connection.execute(statement)

    async with test_engine.connect() as connection:
        async with connection.begin():
            user_id = await _insert_user(
                connection, sub="google|unique", email="unique@example.com"
            )
            menu_item_id = await _insert_menu_item(connection)
            await connection.execute(
                insert(MenuItemDay).values(menu_item_id=menu_item_id, weekday=1)
            )
            await connection.execute(
                insert(Service).values(
                    name="Home cleaning",
                    description="Cleaning",
                    is_active=True,
                    sort_order=2,
                    created_at=_now(),
                    updated_at=_now(),
                )
            )
            await connection.scalar(select(Service.id))
            order_id = await _insert_order(
                connection, user_id=user_id, idempotency_key="unique-key"
            )
            await connection.execute(
                insert(OrderItem).values(
                    order_id=order_id,
                    menu_item_id=menu_item_id,
                    name="Constraint item",
                    quantity=1,
                    unit_price_minor=100,
                )
            )
            await connection.execute(
                insert(Payment).values(
                    order_id=order_id,
                    provider="paystack",
                    reference="unique-reference",
                    provider_transaction_id="unique-transaction",
                    amount_minor=100,
                    currency="NGN",
                    status="initiated",
                    created_at=_now(),
                    updated_at=_now(),
                )
            )

            await assert_rejected(
                connection,
                insert(User).values(
                    provider_sub="google|unique",
                    email="another@example.com",
                    first_name="Duplicate subject",
                    created_at=_now(),
                ),
            )
            await assert_rejected(
                connection,
                insert(User).values(
                    provider_sub="google|another",
                    email="unique@example.com",
                    first_name="Duplicate email",
                    created_at=_now(),
                ),
            )
            await assert_rejected(
                connection,
                insert(MenuItemDay).values(menu_item_id=menu_item_id, weekday=1),
            )
            await assert_rejected(
                connection,
                insert(Order).values(
                    user_id=user_id,
                    status="pending",
                    fulfillment_type="pickup",
                    fulfillment_date=date(2026, 10, 6),
                    contact={"name": "Ada", "phone": "+2348012345678", "address": None},
                    items_total_minor=100,
                    delivery_fee_minor=0,
                    total_minor=100,
                    currency="NGN",
                    idempotency_key="unique-key",
                    created_at=_now(),
                    updated_at=_now(),
                ),
            )
            await assert_rejected(
                connection,
                insert(OrderItem).values(
                    order_id=order_id,
                    menu_item_id=menu_item_id,
                    name="Constraint item",
                    quantity=1,
                    unit_price_minor=100,
                ),
            )
            await assert_rejected(
                connection,
                insert(Payment).values(
                    order_id=order_id,
                    provider="paystack",
                    reference="unique-reference",
                    amount_minor=100,
                    currency="NGN",
                    status="initiated",
                    created_at=_now(),
                    updated_at=_now(),
                ),
            )
            await assert_rejected(
                connection,
                insert(Payment).values(
                    order_id=order_id,
                    provider="paystack",
                    reference="another-reference",
                    provider_transaction_id="unique-transaction",
                    amount_minor=100,
                    currency="NGN",
                    status="initiated",
                    created_at=_now(),
                    updated_at=_now(),
                ),
            )
            await assert_rejected(
                connection,
                insert(Payment).values(
                    order_id=99999,
                    provider="paystack",
                    reference="unknown-order-reference",
                    amount_minor=100,
                    currency="NGN",
                    status="initiated",
                    created_at=_now(),
                    updated_at=_now(),
                ),
            )


async def test_user_role_defaults_to_user_and_rejects_unknown_roles(
    test_engine: AsyncEngine,
) -> None:
    async with test_engine.connect() as connection:
        async with connection.begin():
            user_id = await _insert_user(
                connection, sub="google|role", email="role@example.com"
            )
            with pytest.raises(IntegrityError):
                async with connection.begin_nested():
                    await connection.execute(
                        update(User).where(User.id == user_id).values(role="superuser")
                    )
            role = await connection.scalar(select(User.role).where(User.id == user_id))
    assert role == "user"


async def test_a_menu_item_can_be_served_on_several_days(
    test_engine: AsyncEngine,
) -> None:
    async with test_engine.connect() as connection:
        async with connection.begin():
            menu_item_id = await _insert_menu_item(connection)
            for weekday in (4, 5):
                await connection.execute(
                    insert(MenuItemDay).values(
                        menu_item_id=menu_item_id, weekday=weekday
                    )
                )
            weekdays = set(
                await connection.scalars(
                    select(MenuItemDay.weekday).where(
                        MenuItemDay.menu_item_id == menu_item_id
                    )
                )
            )
    assert weekdays == {4, 5}


async def test_menu_item_days_cascade_delete_with_their_menu_item(
    test_engine: AsyncEngine,
) -> None:
    async with test_engine.connect() as connection:
        async with connection.begin():
            menu_item_id = await _insert_menu_item(connection)
            await connection.execute(
                insert(MenuItemDay).values(menu_item_id=menu_item_id, weekday=1)
            )
            await connection.execute(
                delete(MenuItem).where(MenuItem.id == menu_item_id)
            )
            remaining = await connection.scalar(
                select(MenuItemDay.menu_item_id).where(
                    MenuItemDay.menu_item_id == menu_item_id
                )
            )
    assert remaining is None


async def test_service_request_constraints(test_engine: AsyncEngine) -> None:
    async with test_engine.connect() as connection:
        async with connection.begin():
            user_id = await _insert_user(
                connection, sub="google|requests", email="requests@example.com"
            )
            await connection.execute(
                insert(Service).values(
                    name="Errand running",
                    description="Errands",
                    is_active=True,
                    sort_order=3,
                    created_at=_now(),
                    updated_at=_now(),
                )
            )
            service_id = await connection.scalar(select(Service.id))
            result = await connection.execute(
                insert(ServiceRequest).values(
                    user_id=user_id,
                    service_id=service_id or 1,
                    preferred_date=date(2026, 10, 20),
                    location="Lekki",
                    details="Pick up a parcel",
                    contact_phone="+2348012345678",
                    status="requested",
                    created_at=_now(),
                    updated_at=_now(),
                )
            )
            inserted_key = result.inserted_primary_key
            assert inserted_key is not None
            request_id = int(inserted_key[0])
            with pytest.raises(IntegrityError):
                async with connection.begin_nested():
                    await connection.execute(
                        update(ServiceRequest)
                        .where(ServiceRequest.id == request_id)
                        .values(status="quoted")
                    )
            with pytest.raises(IntegrityError):
                async with connection.begin_nested():
                    await connection.execute(
                        update(ServiceRequest)
                        .where(ServiceRequest.id == request_id)
                        .values(quoted_amount_minor=-1)
                    )
            quoted = await connection.execute(
                update(ServiceRequest)
                .where(ServiceRequest.id == request_id)
                .values(quoted_amount_minor=45000, owner_note="Confirmed by phone")
                .returning(ServiceRequest.quoted_amount_minor)
            )
    assert quoted.scalar_one() == 45000
