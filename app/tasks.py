from app.celery_app import celery_app
from app.core.database import db_session
from app.services.review_service import review_job_sync, review_segment_sync
from app.services.translation_service import translate_job_sync, translate_segment_sync


@celery_app.task(name="healthcheck_task")
def healthcheck_task():
    return {
        "status": "ok",
        "worker": "celery"
    }


@celery_app.task(name="translate_segment_task")
def translate_segment_task(
    segment_id: str,
    force: bool = False,
    timeout_seconds: int = 900,
):
    with db_session() as db:
        return translate_segment_sync(
            db=db,
            segment_id=segment_id,
            force=force,
            timeout_seconds=timeout_seconds,
        )


@celery_app.task(name="translate_job_task")
def translate_job_task(
    job_id: str,
    force: bool = False,
    timeout_seconds: int = 900,
):
    with db_session() as db:
        return translate_job_sync(
            db=db,
            job_id=job_id,
            force=force,
            timeout_seconds=timeout_seconds,
        )


@celery_app.task(name="review_segment_task")
def review_segment_task(
    segment_id: str,
    force: bool = False,
    timeout_seconds: int = 1200,
):
    with db_session() as db:
        return review_segment_sync(
            db=db,
            segment_id=segment_id,
            force=force,
            timeout_seconds=timeout_seconds,
        )


@celery_app.task(name="review_job_task")
def review_job_task(
    job_id: str,
    force: bool = False,
    timeout_seconds: int = 1200,
):
    with db_session() as db:
        return review_job_sync(
            db=db,
            job_id=job_id,
            force=force,
            timeout_seconds=timeout_seconds,
        )
