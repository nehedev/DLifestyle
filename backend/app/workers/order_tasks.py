import asyncio

from celery import shared_task
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.services.expiry import cancel_expired_orders_impl
from app.workers.celery_app import celery_app, worker_engine

OrderSessionFactory = async_sessionmaker(worker_engine, expire_on_commit=False)


@shared_task(
    name="cancel_expired_orders",
    acks_late=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=settings.celery_retry_backoff_max_seconds,
    max_retries=settings.celery_task_max_retries,
)
def cancel_expired_orders() -> None:
    asyncio.run(
        cancel_expired_orders_impl(
            session_factory=OrderSessionFactory,
            enqueue_cancelled_email=lambda order_id: celery_app.send_task(
                "send_order_cancelled_email", args=[order_id]
            ),
        )
    )
