from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import HumanReview, Job, Segment
from app.services.human_review_service import (
    build_review_package,
    human_review_to_dict,
    submit_human_review,
)


router = APIRouter(
    prefix="/human-reviews",
    tags=["human-reviews"],
)


class HumanReviewSubmitRequest(BaseModel):
    decision: str = Field(..., min_length=1)
    reviewer: str = "human"
    human_notes: Optional[str] = None
    revised_text: Optional[str] = None


@router.get("/job/{job_id}/pending")
def list_pending_human_reviews(
    job_id: str,
    db: Session = Depends(get_db),
):
    job = db.get(Job, job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    segments = db.execute(
        select(Segment)
        .where(Segment.job_id == job_id)
        .order_by(Segment.segment_index.asc())
    ).scalars().all()

    pending = []

    for segment in segments:
        latest_human_review = db.execute(
            select(HumanReview)
            .where(HumanReview.segment_id == segment.id)
            .order_by(HumanReview.created_at.desc())
            .limit(1)
        ).scalars().first()

        if segment.status in ["translated", "reviewed"] or latest_human_review is None:
            pending.append(
                {
                    "segment_id": segment.id,
                    "segment_index": segment.segment_index,
                    "source_text": segment.source_text,
                    "translated_text": segment.translated_text,
                    "segment_status": segment.status,
                    "latest_human_decision": latest_human_review.decision if latest_human_review else None,
                }
            )

    return {
        "status": "ok",
        "job_id": job.id,
        "job_status": job.status,
        "current_stage": job.current_stage,
        "count": len(pending),
        "pending": pending,
    }


@router.get("/segment/{segment_id}/package")
def get_human_review_package(
    segment_id: str,
    db: Session = Depends(get_db),
):
    try:
        package = build_review_package(
            db=db,
            segment_id=segment_id,
        )

        return {
            "status": "ok",
            "package": package,
        }

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/segment/{segment_id}/submit")
def submit_segment_human_review(
    segment_id: str,
    request: HumanReviewSubmitRequest,
    db: Session = Depends(get_db),
):
    try:
        return submit_human_review(
            db=db,
            segment_id=segment_id,
            decision=request.decision,
            reviewer=request.reviewer,
            human_notes=request.human_notes,
            revised_text=request.revised_text,
        )

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/job/{job_id}")
def list_job_human_reviews(
    job_id: str,
    db: Session = Depends(get_db),
):
    job = db.get(Job, job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    items = db.execute(
        select(HumanReview)
        .where(HumanReview.job_id == job_id)
        .order_by(HumanReview.created_at.asc())
    ).scalars().all()

    return {
        "status": "ok",
        "job_id": job.id,
        "job_status": job.status,
        "current_stage": job.current_stage,
        "count": len(items),
        "human_reviews": [human_review_to_dict(item) for item in items],
    }


@router.get("/file")
def read_human_review_file(path: str):
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


@router.get("/job/{job_id}/files")
def list_human_review_files(job_id: str):
    review_dir = Path("/app/storage") / "jobs" / job_id / "human_reviews"

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
