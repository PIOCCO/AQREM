"""Shared Celery application (API enqueue + worker consume)."""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery("aqrem", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_default_queue = "default"
celery_app.conf.task_routes = {"worker.app.tasks.ingestion.*": {"queue": "ingestion"}}
celery_app.conf.beat_schedule = {
    "sweep-stuck-documents": {
        "task": "worker.app.tasks.maintenance.sweep_stuck_documents",
        "schedule": 60.0,
    },
}
# Task modules live under /app/worker/app/tasks (second `app` package on PYTHONPATH).
celery_app.autodiscover_tasks(["app.tasks"])
