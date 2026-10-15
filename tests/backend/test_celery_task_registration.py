"""Celery tasks register on backend app.celery_app (worker consumes the same app)."""


def test_ingestion_task_registered_on_celery_app():
    from app.celery_app import celery_app

    assert "worker.app.tasks.ingestion.run_source_sync" in celery_app.tasks
    assert "worker.app.tasks.maintenance.sweep_stuck_documents" in celery_app.tasks
