from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field

from app.models import Order, Payment
from app.schemas.orders import OrderContact
from app.services.admin_orders import AdminOrderDetail

type OrderStatusFilter = Annotated[
    str | None,
    Field(pattern=r"^(pending|paid|preparing|ready|completed|cancelled)$"),
]
type PaymentStatusFilter = Annotated[
    str | None,
    Field(
        pattern=(r"^(initiated|succeeded|failed|needs_review|refund_pending|refunded)$")
    ),
]
type OwnerStatusBody = Annotated[
    str,
    Field(pattern=r"^(preparing|ready|completed|cancelled)$"),
]


class AdminOrderItemResponse(BaseModel):
    id: int
    menu_item_id: int
    name: str
    quantity: int
    unit_price_minor: int


class AdminPaymentResponse(BaseModel):
    id: int
    reference: str
    provider_transaction_id: str | None
    status: str
    amount_minor: int
    currency: str


class AdminOrderResponse(BaseModel):
    id: int
    user_id: int
    status: str
    fulfillment_type: str
    fulfillment_date: date
    contact: OrderContact
    notes: str | None
    items_total_minor: int
    delivery_fee_minor: int
    total_minor: int
    currency: str
    created_at: datetime
    updated_at: datetime
    items: list[AdminOrderItemResponse]
    payments: list[AdminPaymentResponse]


class AdminOrderListResponse(BaseModel):
    id: int
    user_id: int
    status: str
    fulfillment_type: str
    fulfillment_date: date
    total_minor: int
    currency: str
    created_at: datetime


class AdminPaymentListResponse(AdminPaymentResponse):
    order_id: int
    created_at: datetime


def admin_order_response(detail: AdminOrderDetail) -> AdminOrderResponse:
    return AdminOrderResponse(
        id=detail.order.id,
        user_id=detail.order.user_id,
        status=detail.order.status,
        fulfillment_type=detail.order.fulfillment_type,
        fulfillment_date=detail.order.fulfillment_date,
        contact=OrderContact.model_validate(detail.order.contact),
        notes=detail.order.notes,
        items_total_minor=detail.order.items_total_minor,
        delivery_fee_minor=detail.order.delivery_fee_minor,
        total_minor=detail.order.total_minor,
        currency=detail.order.currency,
        created_at=detail.order.created_at,
        updated_at=detail.order.updated_at,
        items=[
            AdminOrderItemResponse(
                id=item.id,
                menu_item_id=item.menu_item_id,
                name=item.name,
                quantity=item.quantity,
                unit_price_minor=item.unit_price_minor,
            )
            for item in detail.items
        ],
        payments=[admin_payment_response(payment) for payment in detail.payments],
    )


def admin_payment_response(payment: Payment) -> AdminPaymentResponse:
    return AdminPaymentResponse(
        id=payment.id,
        reference=payment.reference,
        provider_transaction_id=payment.provider_transaction_id,
        status=payment.status,
        amount_minor=payment.amount_minor,
        currency=payment.currency,
    )


def admin_order_list_response(order: Order) -> AdminOrderListResponse:
    return AdminOrderListResponse(
        id=order.id,
        user_id=order.user_id,
        status=order.status,
        fulfillment_type=order.fulfillment_type,
        fulfillment_date=order.fulfillment_date,
        total_minor=order.total_minor,
        currency=order.currency,
        created_at=order.created_at,
    )


def admin_payment_list_response(payment: Payment) -> AdminPaymentListResponse:
    return AdminPaymentListResponse(
        id=payment.id,
        order_id=payment.order_id,
        reference=payment.reference,
        provider_transaction_id=payment.provider_transaction_id,
        status=payment.status,
        amount_minor=payment.amount_minor,
        currency=payment.currency,
        created_at=payment.created_at,
    )


class AdminOrderStatusBody(BaseModel):
    status: OwnerStatusBody
