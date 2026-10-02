from datetime import UTC, datetime

import pytest
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.base import Base
from app.models import Order, OrderItem, Payment, Product, User


def test_model_tables_and_required_constraints() -> None:
    assert set(Base.metadata.tables) == {
        "users",
        "products",
        "orders",
        "order_items",
        "payments",
    }
    product_constraints = Base.metadata.tables["products"].constraints
    assert {constraint.name for constraint in product_constraints} >= {
        "ck_products_price_minor_nonnegative",
        "ck_products_stock_quantity_nonnegative",
    }
    order_constraints = Base.metadata.tables["orders"].constraints
    assert {constraint.name for constraint in order_constraints} >= {
        "uq_orders_user_id_idempotency_key",
        "ck_orders_valid_status",
    }
    order_item_constraints = Base.metadata.tables["order_items"].constraints
    assert {constraint.name for constraint in order_item_constraints} >= {
        "uq_order_items_order_product",
        "ck_order_items_quantity_positive",
    }
    payment_constraints = Base.metadata.tables["payments"].constraints
    assert {constraint.name for constraint in payment_constraints} >= {
        "uq_payments_provider_transaction",
        "uq_payments_reference",
        "ck_payments_valid_status",
    }


async def test_database_constraints_reject_invalid_values(
    test_engine: AsyncEngine,
) -> None:
    now = datetime.now(UTC)

    async def assert_rejected(connection, statement) -> None:
        with pytest.raises(IntegrityError):
            async with connection.begin_nested():
                await connection.execute(statement)

    async with test_engine.connect() as connection:
        async with connection.begin():
            await connection.execute(
                insert(User).values(
                    auth0_sub="auth0|constraint-test",
                    email="constraint-test@example.com",
                    first_name="Constraint",
                    created_at=now,
                )
            )
            await connection.execute(
                insert(Product).values(
                    name="Constraint product",
                    price_minor=100,
                    stock_quantity=2,
                    is_active=True,
                )
            )
            await connection.execute(
                insert(Order).values(
                    user_id=1,
                    status="pending",
                    total_minor=100,
                    currency="NGN",
                    shipping_address={"name": "Constraint"},
                    created_at=now,
                    updated_at=now,
                )
            )
            await assert_rejected(
                connection,
                insert(Product).values(
                    name="Negative price",
                    price_minor=-1,
                    stock_quantity=1,
                    is_active=True,
                ),
            )
            await assert_rejected(
                connection,
                insert(Product).values(
                    name="Negative stock",
                    price_minor=1,
                    stock_quantity=-1,
                    is_active=True,
                ),
            )
            await assert_rejected(
                connection,
                insert(Order).values(
                    user_id=1,
                    status="unknown",
                    total_minor=100,
                    currency="NGN",
                    shipping_address={"name": "Constraint"},
                    created_at=now,
                    updated_at=now,
                ),
            )
            await assert_rejected(
                connection,
                insert(OrderItem).values(
                    order_id=1,
                    product_id=1,
                    quantity=0,
                    unit_price_minor=100,
                ),
            )
            await assert_rejected(
                connection,
                insert(Payment).values(
                    order_id=1,
                    provider="paystack",
                    reference="invalid-status-reference",
                    amount_minor=100,
                    currency="NGN",
                    status="unknown",
                    created_at=now,
                    updated_at=now,
                ),
            )


async def test_database_unique_and_foreign_key_constraints(
    test_engine: AsyncEngine,
) -> None:
    now = datetime.now(UTC)

    async def assert_rejected(connection, statement) -> None:
        with pytest.raises(IntegrityError):
            async with connection.begin_nested():
                await connection.execute(statement)

    async with test_engine.connect() as connection:
        async with connection.begin():
            await connection.execute(
                insert(User).values(
                    auth0_sub="auth0|unique-test",
                    email="unique-test@example.com",
                    first_name="Unique",
                    created_at=now,
                )
            )
            await connection.execute(
                insert(Product).values(
                    name="Unique product",
                    price_minor=100,
                    stock_quantity=2,
                    is_active=True,
                )
            )
            await connection.execute(
                insert(Order).values(
                    user_id=1,
                    status="pending",
                    total_minor=100,
                    currency="NGN",
                    shipping_address={"name": "Unique"},
                    idempotency_key="unique-key",
                    created_at=now,
                    updated_at=now,
                )
            )
            await connection.execute(
                insert(OrderItem).values(
                    order_id=1,
                    product_id=1,
                    quantity=1,
                    unit_price_minor=100,
                )
            )
            await connection.execute(
                insert(Payment).values(
                    order_id=1,
                    provider="paystack",
                    reference="unique-reference",
                    provider_transaction_id="unique-transaction",
                    amount_minor=100,
                    currency="NGN",
                    status="initiated",
                    created_at=now,
                    updated_at=now,
                )
            )

            await assert_rejected(
                connection,
                insert(User).values(
                    auth0_sub="auth0|unique-test",
                    email="another@example.com",
                    first_name="Duplicate subject",
                    created_at=now,
                ),
            )
            await assert_rejected(
                connection,
                insert(User).values(
                    auth0_sub="auth0|another",
                    email="unique-test@example.com",
                    first_name="Duplicate email",
                    created_at=now,
                ),
            )
            await assert_rejected(
                connection,
                insert(Order).values(
                    user_id=1,
                    status="pending",
                    total_minor=100,
                    currency="NGN",
                    shipping_address={"name": "Unique"},
                    idempotency_key="unique-key",
                    created_at=now,
                    updated_at=now,
                ),
            )
            await assert_rejected(
                connection,
                insert(OrderItem).values(
                    order_id=1,
                    product_id=1,
                    quantity=1,
                    unit_price_minor=100,
                ),
            )
            await assert_rejected(
                connection,
                insert(Payment).values(
                    order_id=1,
                    provider="paystack",
                    reference="unique-reference",
                    amount_minor=100,
                    currency="NGN",
                    status="initiated",
                    created_at=now,
                    updated_at=now,
                ),
            )
            await assert_rejected(
                connection,
                insert(Payment).values(
                    order_id=1,
                    provider="paystack",
                    reference="another-reference",
                    provider_transaction_id="unique-transaction",
                    amount_minor=100,
                    currency="NGN",
                    status="initiated",
                    created_at=now,
                    updated_at=now,
                ),
            )
            await assert_rejected(
                connection,
                insert(Payment).values(
                    order_id=999,
                    provider="paystack",
                    reference="unknown-order-reference",
                    amount_minor=100,
                    currency="NGN",
                    status="initiated",
                    created_at=now,
                    updated_at=now,
                ),
            )

            await connection.execute(
                insert(Payment).values(
                    order_id=1,
                    provider="paystack",
                    reference="null-transaction-one",
                    amount_minor=100,
                    currency="NGN",
                    status="initiated",
                    created_at=now,
                    updated_at=now,
                )
            )
            await connection.execute(
                insert(Payment).values(
                    order_id=1,
                    provider="paystack",
                    reference="null-transaction-two",
                    amount_minor=100,
                    currency="NGN",
                    status="initiated",
                    created_at=now,
                    updated_at=now,
                )
            )
