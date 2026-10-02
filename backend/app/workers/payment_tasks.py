import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.payments.dependencies import get_payment_provider
from app.payments.protocol import PaymentEvent
from app.services.payment_events import (
    process_payment_event_impl,
    refund_payment_impl,
)
from app.workers.celery_app import celery_app, worker_engine

WorkerSessionFactory = async_sessionmaker(worker_engine, expire_on_commit=False)


@celery_app.task(
    name="process_payment_event",
    acks_late=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=settings.celery_retry_backoff_max_seconds,
    max_retries=settings.celery_task_max_retries,
)
def process_payment_event(event: PaymentEvent) -> None:
    asyncio.run(
        process_payment_event_impl(
            event,
            session_factory=WorkerSessionFactory,
            provider=get_payment_provider(),
            enqueue_refund=refund_payment.delay,
        )
    )


@celery_app.task(
    name="refund_payment",
    acks_late=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=settings.celery_retry_backoff_max_seconds,
    max_retries=settings.celery_task_max_retries,
)
def refund_payment(payment_id: int) -> None:
    asyncio.run(
        refund_payment_impl(
            payment_id,
            session_factory=WorkerSessionFactory,
            provider=get_payment_provider(),
        )
    )
