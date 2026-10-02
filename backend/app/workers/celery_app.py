from celery import Celery
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings

celery_app = Celery("ficmart", broker=settings.redis_url)
celery_app.conf.update(task_acks_late=True)
app = celery_app

worker_engine = create_async_engine(
    settings.database_url,
    poolclass=NullPool,
)
