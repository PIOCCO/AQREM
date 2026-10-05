from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery("aqrem", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_default_queue = "default"
celery_app.conf.task_routes = {"worker.app.tasks.ingestion.*": {"queue": "ingestion"}}
celery_app.autodiscover_tasks(["worker.app.tasks"])
