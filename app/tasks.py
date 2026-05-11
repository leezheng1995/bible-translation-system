from app.celery_app import celery_app


@celery_app.task(name="healthcheck_task")
def healthcheck_task():
    return {
        "status": "ok",
        "worker": "celery"
    }
