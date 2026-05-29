from celery import Celery
import os
from app.config import settings

# Initialize Celery
celery_app = Celery(
    "biologics_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

# Auto-discover tasks from modules
celery_app.autodiscover_tasks(["app.tasks"])
