"""Worker CLI compatibility (`celery -A app.celery_app` from /app/worker cwd)."""

from app.celery_app import celery_app

__all__ = ["celery_app"]
