import logging
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentUser, get_current_user
from app.core.cursors import InvalidCursor
from app.db.session import get_session
from app.models import ServiceRequest
from app.payments.dependencies import get_payment_provider
from app.payments.protocol import PaymentProvider
from app.schemas.base import CursorPage
from app.schemas.orders import (
    OrderCreate,
    OrderDetailResponse,
    OrderResponse,
)
from app.schemas.payments import PayResponse
from app.schemas.service_requests import (
    ServiceRequestCreate,
    ServiceRequestResponse,
)
from app.schemas.user import MeResponse
from app.services.orders import (
    IdempotencyKeyReused,
    OrderingClosedForDate,
    OrderNotCancellable,
    OrderNotFound,
    UnavailableMenuItems,
    cancel_order,
    create_order,
    get_order_detail,
    list_orders,
)
from app.services.payments import (
    PaymentInitializationFailed,
    PaymentItemsUnavailable,
    PaymentOrderingClosed,
    PaymentOrderNotFound,
    PaymentOrderNotPending,
    initialize_payment,
)
from app.services.service_requests import (
    IllegalServiceRequestTransition,
    PreferredDateInThePast,
    ServiceNotActive,
    ServiceNotFound,
    ServiceRequestNotFound,
    cancel_service_request,
    create_service_request,
    list_service_requests,
)
from app.services.service_requests import (
    get_service_request as find_service_request,
)
from app.services.store_settings import StoreNotConfigured
from app.workers.celery_app import celery_app

router = APIRouter()
logger = logging.getLogger(__name__)


def _service_request_response(
    request: ServiceRequest,
) -> ServiceRequestResponse:
    return ServiceRequestResponse(
        id=request.id,
        service_id=request.service_id,
        preferred_date=request.preferred_date,
        location=request.location,
        details=request.details,
        contact_phone=request.contact_phone,
        status=request.status,
        quoted_amount_minor=request.quoted_amount_minor,
        owner_note=request.owner_note,
        created_at=request.created_at,
        updated_at=request.updated_at,
    )


@router.get("/me", response_model=MeResponse)
async def get_me(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> MeResponse:
    return MeResponse(
        id=current_user.user.id,
        email=current_user.user.email,
        first_name=current_user.user.first_name,
        last_name=current_user.user.last_name,
        role=current_user.user.role,
    )


@router.post("/orders", response_model=OrderResponse)
async def post_order(
    request: OrderCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key", min_length=1, max_length=255),
    ] = None,
) -> OrderResponse:
    try:
        return await create_order(
            session,
            user=current_user.user,
            request=request,
            idempotency_key=idempotency_key,
        )
    except StoreNotConfigured as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="store_not_configured",
        ) from error
    except OrderingClosedForDate as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="ordering_closed_for_date",
        ) from error
    except UnavailableMenuItems as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"unavailable_menu_item_ids": error.menu_item_ids},
        ) from error
    except IdempotencyKeyReused as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="idempotency_key_reused",
        ) from error


@router.get("/orders", response_model=CursorPage[OrderResponse])
async def get_orders(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
) -> CursorPage[OrderResponse]:
    try:
        return await list_orders(
            session,
            user_id=current_user.user.id,
            limit=limit,
            cursor=cursor,
        )
    except InvalidCursor as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_cursor",
        ) from error


@router.get("/orders/{order_id}", response_model=OrderDetailResponse)
async def get_order_by_id(
    order_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OrderDetailResponse:
    order = await get_order_detail(
        session,
        user_id=current_user.user.id,
        order_id=order_id,
    )
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return order


@router.post("/orders/{order_id}/cancel", response_model=OrderResponse)
async def post_cancel_order(
    order_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OrderResponse:
    try:
        return await cancel_order(
            session,
            user_id=current_user.user.id,
            order_id=order_id,
        )
    except OrderNotFound as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    except OrderNotCancellable as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="order_not_pending",
        ) from error


@router.post("/orders/{order_id}/pay", response_model=PayResponse)
async def post_pay_order(
    order_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    provider: Annotated[PaymentProvider, Depends(get_payment_provider)],
) -> PayResponse:
    try:
        authorization_url = await initialize_payment(
            session,
            user=current_user.user,
            order_id=order_id,
            provider=provider,
        )
    except PaymentOrderNotFound as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    except PaymentOrderNotPending as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="order_not_pending",
        ) from error
    except PaymentOrderingClosed as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="ordering_closed_for_date",
        ) from error
    except PaymentItemsUnavailable as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"unavailable_menu_item_ids": error.menu_item_ids},
        ) from error
    except PaymentInitializationFailed as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="payment_initialization_failed",
        ) from error
    return PayResponse(authorization_url=authorization_url)


@router.post("/webhooks/paystack", status_code=status.HTTP_200_OK)
async def post_paystack_webhook(
    request: Request,
    provider: Annotated[PaymentProvider, Depends(get_payment_provider)],
    signature: Annotated[str | None, Header(alias="x-paystack-signature")] = None,
) -> Response:
    raw_body = await request.body()
    if signature is None or not provider.verify_webhook_signature(raw_body, signature):
        logger.warning("webhook.invalid_signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_signature",
        )

    event = provider.parse_webhook(raw_body)
    if event["event_type"] == "ignored":
        logger.info("webhook.event_ignored")
        return Response(status_code=status.HTTP_200_OK)
    if event["event_type"] == "noop":
        return Response(status_code=status.HTTP_200_OK)

    try:
        celery_app.send_task("process_payment_event", args=[event])
    except Exception as error:
        logger.error("webhook.enqueue_failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="webhook_enqueue_failed",
        ) from error
    return Response(status_code=status.HTTP_200_OK)


@router.post("/service-requests", response_model=ServiceRequestResponse)
async def post_service_request(
    body: ServiceRequestCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ServiceRequestResponse:
    try:
        request = await create_service_request(
            session,
            user=current_user.user,
            service_id=body.service_id,
            preferred_date=body.preferred_date,
            location=body.location,
            details=body.details,
            contact_phone=body.contact_phone,
        )
    except ServiceNotFound as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    except ServiceNotActive as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="service_not_active"
        ) from error
    except PreferredDateInThePast as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="preferred_date_in_the_past",
        ) from error
    return _service_request_response(request)


@router.get("/service-requests", response_model=CursorPage[ServiceRequestResponse])
async def get_service_requests(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    request_status: Annotated[
        str | None,
        Query(
            alias="status",
            pattern=r"^(requested|contacted|confirmed|completed|cancelled)$",
        ),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
) -> CursorPage[ServiceRequestResponse]:
    try:
        requests, next_cursor = await list_service_requests(
            session,
            user_id=current_user.user.id,
            status=request_status,
            limit=limit,
            cursor=cursor,
        )
    except InvalidCursor as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_cursor"
        ) from error
    return CursorPage(
        items=[_service_request_response(request) for request in requests],
        next_cursor=next_cursor,
    )


@router.get("/service-requests/{request_id}", response_model=ServiceRequestResponse)
async def get_service_request_by_id(
    request_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ServiceRequestResponse:
    request = await find_service_request(
        session, request_id=request_id, user_id=current_user.user.id
    )
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return _service_request_response(request)


@router.post(
    "/service-requests/{request_id}/cancel", response_model=ServiceRequestResponse
)
async def post_cancel_service_request(
    request_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ServiceRequestResponse:
    try:
        request = await cancel_service_request(
            session,
            request_id=request_id,
            user_id=current_user.user.id,
        )
    except ServiceRequestNotFound as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    except IllegalServiceRequestTransition as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="service_request_not_cancellable",
        ) from error
    return _service_request_response(request)
