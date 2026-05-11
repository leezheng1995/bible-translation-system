from celery import Celery

from app.core.settings import get_settings


settings = get_settings()

celery_app = Celery(
    "bible_translation_worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks"],
)

celery_app.conf.broker_connection_retry_on_startup = True
