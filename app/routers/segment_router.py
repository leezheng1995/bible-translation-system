from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import AuditLog, FileRecord, Job, Segment
from app.services.segmenter import split_into_segments


router = APIRouter(
    prefix="/segments",
    tags=["segments"],
)


class SegmentSourceRequest(BaseModel):
    force: bool = False


def segment_to_dict(segment: Segment) -> dict:
    return {
        "id": segment.id,
        "job_id": segment.job_id,
        "file_id": segment.file_id,
        "book": segment.book,
        "chapter": segment.chapter,
        "verse_start": segment.verse_start,
        "verse_end": segment.verse_end,
        "segment_index": segment.segment_index,
        "source_text": segment.source_text,
        "translated_text": segment.translated_text,
        "status": segment.status,
        "created_at": segment.created_at.isoformat() if segment.created_at else None,
        "updated_at": segment.updated_at.isoformat() if segment.updated_at else None,
    }


def add_audit_log(
    db: Session,
    job_id: Optional[str],
    event_type: str,
    stage: str,
    message: str,
    payload_json: Optional[str] = None,
) -> None:
    db.add(
        AuditLog(
            job_id=job_id,
            event_type=event_type,
            stage=stage,
            message=message,
            payload_json=payload_json,
        )
    )


@router.get("/job/{job_id}")
def list_job_segments(
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

    return {
        "status": "ok",
        "job_id": job_id,
        "job_status": job.status,
        "current_stage": job.current_stage,
        "count": len(segments),
        "segments": [segment_to_dict(segment) for segment in segments],
    }


@router.post("/job/{job_id}/segment-source")
def segment_job_source(
    job_id: str,
    request: SegmentSourceRequest | None = None,
    force: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    final_force = force or (request.force if request else False)

    job = db.get(Job, job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    existing_segments = db.execute(
        select(Segment).where(Segment.job_id == job_id)
    ).scalars().all()

    if existing_segments and not final_force:
        return {
            "status": "ok",
            "duplicate": True,
            "message": "Segments already exist. Use force=true to recreate.",
            "job_id": job_id,
            "count": len(existing_segments),
            "segments": [segment_to_dict(segment) for segment in existing_segments],
        }

    if existing_segments and final_force:
        db.execute(delete(Segment).where(Segment.job_id == job_id))
        db.flush()

    source_file = db.execute(
        select(FileRecord).where(
            FileRecord.job_id == job_id,
            FileRecord.file_role == "source",
        )
    ).scalar_one_or_none()

    if not source_file:
        raise HTTPException(status_code=404, detail="Source file not found")

    if not source_file.local_path:
        raise HTTPException(
            status_code=400,
            detail="Source file has no local_path. Please run /files/job/{job_id}/download-source first.",
        )

    source_path = Path(source_file.local_path)

    if not source_path.exists():
        raise HTTPException(status_code=404, detail=f"Local source file not found: {source_file.local_path}")

    source_text = source_path.read_text(encoding="utf-8")
    segment_items = split_into_segments(source_text)

    if not segment_items:
        raise HTTPException(status_code=400, detail="No segments generated from source file")

    created_segments = []

    for item in segment_items:
        segment = Segment(
            job_id=job.id,
            file_id=source_file.id,
            book=item.book,
            chapter=item.chapter,
            verse_start=item.verse_start,
            verse_end=item.verse_end,
            segment_index=item.segment_index,
            source_text=item.source_text,
            translated_text=None,
            status="created",
        )

        db.add(segment)
        created_segments.append(segment)

    job.current_stage = "segmented"
    if job.status == "created":
        job.status = "processing"
    job.updated_at = datetime.utcnow()

    add_audit_log(
        db=db,
        job_id=job.id,
        event_type="source_segmented",
        stage="segmented",
        message=f"Source file segmented into {len(created_segments)} segment(s).",
    )

    db.commit()

    for segment in created_segments:
        db.refresh(segment)

    db.refresh(job)

    return {
        "status": "ok",
        "duplicate": False,
        "job_id": job.id,
        "job_status": job.status,
        "current_stage": job.current_stage,
        "count": len(created_segments),
        "segments": [segment_to_dict(segment) for segment in created_segments],
    }


@router.get("/{segment_id}")
def get_segment(
    segment_id: str,
    db: Session = Depends(get_db),
):
    segment = db.get(Segment, segment_id)

    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")

    return {
        "status": "ok",
        "segment": segment_to_dict(segment),
    }


@router.delete("/job/{job_id}")
def delete_job_segments(
    job_id: str,
    db: Session = Depends(get_db),
):
    job = db.get(Job, job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    existing_segments = db.execute(
        select(Segment).where(Segment.job_id == job_id)
    ).scalars().all()

    count = len(existing_segments)

    db.execute(delete(Segment).where(Segment.job_id == job_id))

    job.current_stage = "segments_deleted"
    job.updated_at = datetime.utcnow()

    add_audit_log(
        db=db,
        job_id=job.id,
        event_type="segments_deleted",
        stage="segments_deleted",
        message=f"Deleted {count} segment(s).",
    )

    db.commit()

    return {
        "status": "ok",
        "job_id": job_id,
        "deleted_count": count,
    }
