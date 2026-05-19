import json
from pathlib import Path
from typing import Optional

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.core.database import get_db
from app.models import Job, Segment, TranslationVersion
from app.services.translation_service import (
    translate_job_sync,
    translate_segment_sync,
    translation_version_to_dict,
)


router = APIRouter(
    prefix="/translations",
    tags=["translations"],
)


class TranslationRunRequest(BaseModel):
    force: bool = False
    timeout_seconds: int = 900


def segment_to_dict(segment: Segment) -> dict:
    return {
        "id": segment.id,
        "job_id": segment.job_id,
        "segment_index": segment.segment_index,
        "source_text": segment.source_text,
        "translated_text": segment.translated_text,
        "status": segment.status,
        "updated_at": segment.updated_at.isoformat() if segment.updated_at else None,
    }


@router.get("/job/{job_id}")
def list_job_translations(
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

    versions = db.execute(
        select(TranslationVersion)
        .where(TranslationVersion.job_id == job_id)
        .order_by(TranslationVersion.created_at.asc())
    ).scalars().all()

    return {
        "status": "ok",
        "job_id": job.id,
        "job_status": job.status,
        "current_stage": job.current_stage,
        "segments_count": len(segments),
        "versions_count": len(versions),
        "segments": [segment_to_dict(segment) for segment in segments],
        "translation_versions": [
            translation_version_to_dict(version)
            for version in versions
        ],
    }


@router.get("/segment/{segment_id}")
def list_segment_translations(
    segment_id: str,
    db: Session = Depends(get_db),
):
    segment = db.get(Segment, segment_id)

    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")

    versions = db.execute(
        select(TranslationVersion)
        .where(TranslationVersion.segment_id == segment_id)
        .order_by(TranslationVersion.version_no.asc())
    ).scalars().all()

    return {
        "status": "ok",
        "segment": segment_to_dict(segment),
        "versions_count": len(versions),
        "translation_versions": [
            translation_version_to_dict(version)
            for version in versions
        ],
    }


@router.post("/segment/{segment_id}/run")
def run_segment_translation_sync(
    segment_id: str,
    request: TranslationRunRequest | None = None,
    db: Session = Depends(get_db),
):
    force = request.force if request else False
    timeout_seconds = request.timeout_seconds if request else 900

    try:
        return translate_segment_sync(
            db=db,
            segment_id=segment_id,
            force=force,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/job/{job_id}/run")
def run_job_translation_sync(
    job_id: str,
    request: TranslationRunRequest | None = None,
    db: Session = Depends(get_db),
):
    force = request.force if request else False
    timeout_seconds = request.timeout_seconds if request else 900

    try:
        return translate_job_sync(
            db=db,
            job_id=job_id,
            force=force,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/segment/{segment_id}/enqueue")
def enqueue_segment_translation(
    segment_id: str,
    request: TranslationRunRequest | None = None,
    db: Session = Depends(get_db),
):
    segment = db.get(Segment, segment_id)

    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")

    force = request.force if request else False
    timeout_seconds = request.timeout_seconds if request else 900

    task = celery_app.send_task(
        "translate_segment_task",
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
def enqueue_job_translation(
    job_id: str,
    request: TranslationRunRequest | None = None,
    db: Session = Depends(get_db),
):
    job = db.get(Job, job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    force = request.force if request else False
    timeout_seconds = request.timeout_seconds if request else 900

    task = celery_app.send_task(
        "translate_job_task",
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
def get_translation_task_status(task_id: str):
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
def list_translation_files(job_id: str):
    translation_dir = Path("/app/storage") / "jobs" / job_id / "translations"

    if not translation_dir.exists():
        return {
            "status": "ok",
            "job_id": job_id,
            "count": 0,
            "files": [],
        }

    files = sorted(translation_dir.glob("*"))

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
def read_translation_file(path: str):
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
