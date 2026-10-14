from celery import Celery
from celery.signals import worker_process_init

from app.core.config import get_settings
from app.core.container_config import validate_container_startup

settings = get_settings()

celery_app = Celery("aqrem", broker=settings.redis_url, backend=settings.redis_url)


@worker_process_init.connect
def _validate_worker_env(**_kwargs) -> None:
    validate_container_startup("worker", get_settings())
celery_app.conf.task_default_queue = "default"
celery_app.conf.task_routes = {"worker.app.tasks.ingestion.*": {"queue": "ingestion"}}
celery_app.autodiscover_tasks(["worker.app.tasks"])
