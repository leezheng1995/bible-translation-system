from pathlib import Path

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.core.database import get_db
from app.models import Job, Review, Segment
from app.services.review_service import review_job_sync, review_segment_sync, review_to_dict


router = APIRouter(
    prefix="/reviews",
    tags=["reviews"],
)


class ReviewRunRequest(BaseModel):
    force: bool = False
    timeout_seconds: int = 1200


@router.get("/job/{job_id}")
def list_job_reviews(
    job_id: str,
    db: Session = Depends(get_db),
):
    job = db.get(Job, job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    reviews = db.execute(
        select(Review)
        .where(Review.job_id == job_id)
        .order_by(Review.created_at.asc())
    ).scalars().all()

    return {
        "status": "ok",
        "job_id": job.id,
        "job_status": job.status,
        "current_stage": job.current_stage,
        "count": len(reviews),
        "reviews": [review_to_dict(item) for item in reviews],
    }


@router.get("/segment/{segment_id}")
def list_segment_reviews(
    segment_id: str,
    db: Session = Depends(get_db),
):
    segment = db.get(Segment, segment_id)

    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")

    reviews = db.execute(
        select(Review)
        .where(Review.segment_id == segment_id)
        .order_by(Review.created_at.asc())
    ).scalars().all()

    return {
        "status": "ok",
        "segment_id": segment.id,
        "job_id": segment.job_id,
        "count": len(reviews),
        "reviews": [review_to_dict(item) for item in reviews],
    }


@router.post("/segment/{segment_id}/run")
def run_segment_review_sync(
    segment_id: str,
    request: ReviewRunRequest | None = None,
    db: Session = Depends(get_db),
):
    force = request.force if request else False
    timeout_seconds = request.timeout_seconds if request else 1200

    try:
        return review_segment_sync(
            db=db,
            segment_id=segment_id,
            force=force,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/job/{job_id}/run")
def run_job_review_sync(
    job_id: str,
    request: ReviewRunRequest | None = None,
    db: Session = Depends(get_db),
):
    force = request.force if request else False
    timeout_seconds = request.timeout_seconds if request else 1200

    try:
        return review_job_sync(
            db=db,
            job_id=job_id,
            force=force,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/segment/{segment_id}/enqueue")
def enqueue_segment_review(
    segment_id: str,
    request: ReviewRunRequest | None = None,
    db: Session = Depends(get_db),
):
    segment = db.get(Segment, segment_id)

    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")

    force = request.force if request else False
    timeout_seconds = request.timeout_seconds if request else 1200

    task = celery_app.send_task(
        "review_segment_task",
        kwargs={
            "segment_id": segment_id,
            "force": force,
            "timeout_seconds": timeout_seconds,
        },
    )

    return {
        "status": "queued",
        "task_id": task.id,
        "segment_id": segment_id,
        "job_id": segment.job_id,
    }


@router.post("/job/{job_id}/enqueue")
def enqueue_job_review(
    job_id: str,
    request: ReviewRunRequest | None = None,
    db: Session = Depends(get_db),
):
    job = db.get(Job, job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    force = request.force if request else False
    timeout_seconds = request.timeout_seconds if request else 1200

    task = celery_app.send_task(
        "review_job_task",
        kwargs={
            "job_id": job_id,
            "force": force,
            "timeout_seconds": timeout_seconds,
        },
    )

    return {
        "status": "queued",
        "task_id": task.id,
        "job_id": job_id,
    }


@router.get("/tasks/{task_id}")
def get_review_task_status(task_id: str):
    result = AsyncResult(task_id, app=celery_app)

    response = {
        "task_id": task_id,
        "state": result.state,
        "ready": result.ready(),
        "successful": result.successful() if result.ready() else False,
    }

    if result.ready():
        try:
            response["result"] = result.result
        except Exception as exc:
            response["error"] = str(exc)

    return response


@router.get("/job/{job_id}/files")
def list_review_files(job_id: str):
    review_dir = Path("/app/storage") / "jobs" / job_id / "reviews"

    if not review_dir.exists():
        return {
            "status": "ok",
            "job_id": job_id,
            "count": 0,
            "files": [],
        }

    files = sorted(review_dir.glob("*"))

    return {
        "status": "ok",
        "job_id": job_id,
        "count": len(files),
        "files": [
            {
                "file_name": file.name,
                "path": str(file),
                "size": file.stat().st_size,
            }
            for file in files
            if file.is_file()
        ],
    }


@router.get("/file")
def read_review_file(path: str):
    target = Path(path)

    if not target.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    resolved = target.resolve()
    storage_root = Path("/app/storage").resolve()

    if storage_root not in resolved.parents and resolved != storage_root:
        raise HTTPException(status_code=400, detail="Only files under /app/storage are allowed")

    content = target.read_text(encoding="utf-8")

    return {
        "status": "ok",
        "path": str(target),
        "content_length": len(content),
        "content": content,
    }
