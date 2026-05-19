from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import AuditLog, FileRecord, Job
from app.services.google_drive_client import GoogleDriveClient


router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
)


class CreateJobRequest(BaseModel):
    source_file_id: Optional[str] = None
    source_file_name: str = Field(..., min_length=1)
    mime_type: Optional[str] = None
    drive_url: Optional[str] = None
    priority: int = 5
    force: bool = False


class StatusMessageRequest(BaseModel):
    message: Optional[str] = None
    error_message: Optional[str] = None


def job_to_dict(job: Job) -> dict:
    return {
        "id": job.id,
        "source_file_id": job.source_file_id,
        "source_file_name": job.source_file_name,
        "status": job.status,
        "current_stage": job.current_stage,
        "priority": job.priority,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "error_message": job.error_message,
    }


def file_to_dict(file_record: FileRecord) -> dict:
    return {
        "id": file_record.id,
        "job_id": file_record.job_id,
        "drive_file_id": file_record.drive_file_id,
        "file_name": file_record.file_name,
        "mime_type": file_record.mime_type,
        "file_role": file_record.file_role,
        "drive_url": file_record.drive_url,
        "local_path": file_record.local_path,
        "status": file_record.status,
        "created_at": file_record.created_at.isoformat() if file_record.created_at else None,
        "updated_at": file_record.updated_at.isoformat() if file_record.updated_at else None,
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


def create_job_record(
    db: Session,
    source_file_id: Optional[str],
    source_file_name: str,
    mime_type: Optional[str],
    drive_url: Optional[str],
    priority: int = 5,
    force: bool = False,
) -> tuple[Job, FileRecord, bool]:
    if source_file_id and not force:
        existing_file = db.execute(
            select(FileRecord).where(FileRecord.drive_file_id == source_file_id)
        ).scalar_one_or_none()

        if existing_file and existing_file.job_id:
            existing_job = db.get(Job, existing_file.job_id)
            if existing_job:
                return existing_job, existing_file, True

    job = Job(
        source_file_id=source_file_id,
        source_file_name=source_file_name,
        status="created",
        current_stage="created",
        priority=priority,
    )

    db.add(job)
    db.flush()

    file_record = FileRecord(
        job_id=job.id,
        drive_file_id=source_file_id,
        file_name=source_file_name,
        mime_type=mime_type,
        file_role="source",
        drive_url=drive_url,
        status="discovered",
    )

    db.add(file_record)

    add_audit_log(
        db=db,
        job_id=job.id,
        event_type="job_created",
        stage="created",
        message=f"Job created from source file: {source_file_name}",
    )

    db.commit()
    db.refresh(job)
    db.refresh(file_record)

    return job, file_record, False


@router.post("")
def create_job(request: CreateJobRequest, db: Session = Depends(get_db)):
    job, file_record, duplicate = create_job_record(
        db=db,
        source_file_id=request.source_file_id,
        source_file_name=request.source_file_name,
        mime_type=request.mime_type,
        drive_url=request.drive_url,
        priority=request.priority,
        force=request.force,
    )

    return {
        "status": "ok",
        "duplicate": duplicate,
        "job": job_to_dict(job),
        "file": file_to_dict(file_record),
    }


@router.post("/discover-from-drive")
def discover_jobs_from_drive(db: Session = Depends(get_db)):
    client = GoogleDriveClient()
    tasks = client.list_inbox_tasks()

    created = []
    duplicates = []

    for task in tasks:
        job, file_record, duplicate = create_job_record(
            db=db,
            source_file_id=task.get("id"),
            source_file_name=task.get("name", "unknown"),
            mime_type=task.get("mime_type"),
            drive_url=task.get("web_view_link"),
            priority=5,
            force=False,
        )

        item = {
            "job": job_to_dict(job),
            "file": file_to_dict(file_record),
        }

        if duplicate:
            duplicates.append(item)
        else:
            created.append(item)

    return {
        "status": "ok",
        "drive_task_count": len(tasks),
        "created_count": len(created),
        "duplicate_count": len(duplicates),
        "created": created,
        "duplicates": duplicates,
    }


@router.get("")
def list_jobs(
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    stmt = select(Job).order_by(desc(Job.created_at)).limit(limit)

    if status:
        stmt = select(Job).where(Job.status == status).order_by(desc(Job.created_at)).limit(limit)

    jobs = db.execute(stmt).scalars().all()

    return {
        "count": len(jobs),
        "jobs": [job_to_dict(job) for job in jobs],
    }


@router.get("/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    files = db.execute(
        select(FileRecord).where(FileRecord.job_id == job_id)
    ).scalars().all()

    return {
        "status": "ok",
        "job": job_to_dict(job),
        "files": [file_to_dict(file_record) for file_record in files],
    }


@router.post("/{job_id}/start")
def start_job(
    job_id: str,
    request: StatusMessageRequest | None = None,
    db: Session = Depends(get_db),
):
    job = db.get(Job, job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job.status = "processing"
    job.current_stage = "started"
    job.started_at = job.started_at or datetime.utcnow()
    job.updated_at = datetime.utcnow()
    job.error_message = None

    add_audit_log(
        db=db,
        job_id=job.id,
        event_type="job_started",
        stage="started",
        message=(request.message if request and request.message else "Job started"),
    )

    db.commit()
    db.refresh(job)

    return {
        "status": "ok",
        "job": job_to_dict(job),
    }


@router.post("/{job_id}/retry")
def retry_job(
    job_id: str,
    request: StatusMessageRequest | None = None,
    db: Session = Depends(get_db),
):
    job = db.get(Job, job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job.status = "retrying"
    job.current_stage = "retry_requested"
    job.updated_at = datetime.utcnow()
    job.error_message = None

    add_audit_log(
        db=db,
        job_id=job.id,
        event_type="job_retry_requested",
        stage="retry_requested",
        message=(request.message if request and request.message else "Job retry requested"),
    )

    db.commit()
    db.refresh(job)

    return {
        "status": "ok",
        "job": job_to_dict(job),
    }


@router.post("/{job_id}/complete")
def complete_job(
    job_id: str,
    request: StatusMessageRequest | None = None,
    db: Session = Depends(get_db),
):
    job = db.get(Job, job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job.status = "completed"
    job.current_stage = "completed"
    job.completed_at = datetime.utcnow()
    job.updated_at = datetime.utcnow()

    add_audit_log(
        db=db,
        job_id=job.id,
        event_type="job_completed",
        stage="completed",
        message=(request.message if request and request.message else "Job completed"),
    )

    db.commit()
    db.refresh(job)

    return {
        "status": "ok",
        "job": job_to_dict(job),
    }


@router.post("/{job_id}/fail")
def fail_job(
    job_id: str,
    request: StatusMessageRequest,
    db: Session = Depends(get_db),
):
    job = db.get(Job, job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    error_message = request.error_message or request.message or "Unknown error"

    job.status = "failed"
    job.current_stage = "failed"
    job.error_message = error_message
    job.updated_at = datetime.utcnow()

    add_audit_log(
        db=db,
        job_id=job.id,
        event_type="job_failed",
        stage="failed",
        message=error_message,
    )

    db.commit()
    db.refresh(job)

    return {
        "status": "ok",
        "job": job_to_dict(job),
    }
