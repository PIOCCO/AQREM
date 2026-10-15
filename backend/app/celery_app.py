"""Shared Celery application (API enqueue + worker consume)."""

import os

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery("aqrem", broker=settings.redis_url, backend=settings.redis_url)
# Beat runs as non-root in Docker; default cwd (/app/backend) is not writable.
celery_app.conf.beat_schedule_filename = os.environ.get(
    "CELERY_BEAT_SCHEDULE_FILE",
    "/tmp/celerybeat-schedule",
)
celery_app.conf.task_default_queue = "default"
celery_app.conf.task_routes = {"worker.app.tasks.ingestion.*": {"queue": "ingestion"}}
celery_app.conf.beat_schedule = {
    "sweep-stuck-documents": {
        "task": "worker.app.tasks.maintenance.sweep_stuck_documents",
        "schedule": 60.0,
    },
}
celery_app.conf.include = ["app.tasks.ingestion", "app.tasks.maintenance"]

# Import task modules so @celery_app.task registers before the worker consumes queues.
import app.tasks.ingestion  # noqa: E402, F401
import app.tasks.maintenance  # noqa: E402, F401
