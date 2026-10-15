"""Celery tasks register on backend app.celery_app (worker consumes the same app)."""


def test_ingestion_task_registered_on_celery_app():
    from app.celery_app import celery_app

    import app.tasks.ingestion  # noqa: F401
    import app.tasks.maintenance  # noqa: F401

    assert "worker.app.tasks.ingestion.run_source_sync" in celery_app.tasks
