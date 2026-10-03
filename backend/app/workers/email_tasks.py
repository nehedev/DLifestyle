import asyncio

from celery import shared_task
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.emails.delivery import (
    send_new_order_email_impl,
    send_new_service_request_email_impl,
    send_order_cancelled_email_impl,
    send_order_confirmation_email_impl,
    send_payment_failed_email_impl,
    send_request_received_email_impl,
    send_welcome_email_impl,
)
from app.emails.resend import ResendClient
from app.workers.celery_app import worker_engine

EmailSessionFactory = async_sessionmaker(worker_engine, expire_on_commit=False)
resend_client = ResendClient()


@shared_task(
    name="send_welcome_email",
    acks_late=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=settings.celery_retry_backoff_max_seconds,
    max_retries=settings.celery_task_max_retries,
)
def send_welcome_email(user_id: int) -> None:
    asyncio.run(
        send_welcome_email_impl(
            user_id,
            session_factory=EmailSessionFactory,
            client=resend_client,
        )
    )


@shared_task(
    name="send_order_confirmation_email",
    acks_late=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=settings.celery_retry_backoff_max_seconds,
    max_retries=settings.celery_task_max_retries,
)
def send_order_confirmation_email(order_id: int) -> None:
    asyncio.run(
        send_order_confirmation_email_impl(
            order_id,
            session_factory=EmailSessionFactory,
            client=resend_client,
        )
    )


@shared_task(
    name="send_payment_failed_email",
    acks_late=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=settings.celery_retry_backoff_max_seconds,
    max_retries=settings.celery_task_max_retries,
)
def send_payment_failed_email(payment_id: int) -> None:
    asyncio.run(
        send_payment_failed_email_impl(
            payment_id,
            session_factory=EmailSessionFactory,
            client=resend_client,
        )
    )


@shared_task(
    name="send_order_cancelled_email",
    acks_late=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=settings.celery_retry_backoff_max_seconds,
    max_retries=settings.celery_task_max_retries,
)
def send_order_cancelled_email(order_id: int) -> None:
    asyncio.run(
        send_order_cancelled_email_impl(
            order_id,
            session_factory=EmailSessionFactory,
            client=resend_client,
        )
    )


@shared_task(
    name="send_new_order_email",
    acks_late=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=settings.celery_retry_backoff_max_seconds,
    max_retries=settings.celery_task_max_retries,
)
def send_new_order_email(order_id: int) -> None:
    asyncio.run(
        send_new_order_email_impl(
            order_id,
            session_factory=EmailSessionFactory,
            client=resend_client,
        )
    )


@shared_task(
    name="send_request_received_email",
    acks_late=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=settings.celery_retry_backoff_max_seconds,
    max_retries=settings.celery_task_max_retries,
)
def send_request_received_email(request_id: int) -> None:
    asyncio.run(
        send_request_received_email_impl(
            request_id,
            session_factory=EmailSessionFactory,
            client=resend_client,
        )
    )


@shared_task(
    name="send_new_service_request_email",
    acks_late=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=settings.celery_retry_backoff_max_seconds,
    max_retries=settings.celery_task_max_retries,
)
def send_new_service_request_email(request_id: int) -> None:
    asyncio.run(
        send_new_service_request_email_impl(
            request_id,
            session_factory=EmailSessionFactory,
            client=resend_client,
        )
    )
