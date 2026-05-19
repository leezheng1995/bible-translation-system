from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import AuditLog, FileRecord, Job
from app.services.google_drive_client import GoogleDriveClient


router = APIRouter(
    prefix="/files",
    tags=["files"],
)


STORAGE_ROOT = Path("/app/storage")


def file_to_dict(file_record: FileRecord) -> dict:
    local_exists = False

    if file_record.local_path:
        local_exists = Path(file_record.local_path).exists()

    return {
        "id": file_record.id,
        "job_id": file_record.job_id,
        "drive_file_id": file_record.drive_file_id,
        "file_name": file_record.file_name,
        "mime_type": file_record.mime_type,
        "file_role": file_record.file_role,
        "drive_url": file_record.drive_url,
        "local_path": file_record.local_path,
        "local_exists": local_exists,
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


@router.get("")
def list_files(
    job_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=300),
    db: Session = Depends(get_db),
):
    stmt = select(FileRecord).order_by(desc(FileRecord.created_at)).limit(limit)

    if job_id and status:
        stmt = (
            select(FileRecord)
            .where(FileRecord.job_id == job_id, FileRecord.status == status)
            .order_by(desc(FileRecord.created_at))
            .limit(limit)
        )
    elif job_id:
        stmt = (
            select(FileRecord)
            .where(FileRecord.job_id == job_id)
            .order_by(desc(FileRecord.created_at))
            .limit(limit)
        )
    elif status:
        stmt = (
            select(FileRecord)
            .where(FileRecord.status == status)
            .order_by(desc(FileRecord.created_at))
            .limit(limit)
        )

    files = db.execute(stmt).scalars().all()

    return {
        "count": len(files),
        "files": [file_to_dict(file_record) for file_record in files],
    }


@router.get("/job/{job_id}")
def list_job_files(
    job_id: str,
    db: Session = Depends(get_db),
):
    job = db.get(Job, job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    files = db.execute(
        select(FileRecord).where(FileRecord.job_id == job_id)
    ).scalars().all()

    return {
        "status": "ok",
        "job_id": job_id,
        "job_status": job.status,
        "current_stage": job.current_stage,
        "count": len(files),
        "files": [file_to_dict(file_record) for file_record in files],
    }


@router.post("/job/{job_id}/download-source")
def download_job_source(
    job_id: str,
    db: Session = Depends(get_db),
):
    job = db.get(Job, job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    source_file = db.execute(
        select(FileRecord).where(
            FileRecord.job_id == job_id,
            FileRecord.file_role == "source",
        )
    ).scalar_one_or_none()

    if not source_file:
        raise HTTPException(status_code=404, detail="Source file not found")

    if not source_file.drive_file_id:
        raise HTTPException(status_code=400, detail="Source file has no Google Drive file id")

    client = GoogleDriveClient()

    source_text = client.download_file_as_text(
        file_id=source_file.drive_file_id,
        mime_type=source_file.mime_type,
    )

    job_storage_dir = STORAGE_ROOT / "jobs" / job_id
    job_storage_dir.mkdir(parents=True, exist_ok=True)

    local_path = job_storage_dir / "source.txt"
    local_path.write_text(source_text, encoding="utf-8")

    source_file.local_path = str(local_path)
    source_file.status = "downloaded"
    source_file.updated_at = datetime.utcnow()

    job.current_stage = "source_downloaded"
    if job.status == "created":
        job.status = "processing"
    job.updated_at = datetime.utcnow()

    add_audit_log(
        db=db,
        job_id=job.id,
        event_type="source_downloaded",
        stage="source_downloaded",
        message=f"Source file downloaded to {local_path}",
    )

    db.commit()
    db.refresh(source_file)
    db.refresh(job)

    return {
        "status": "ok",
        "job_id": job.id,
        "job_status": job.status,
        "current_stage": job.current_stage,
        "file": file_to_dict(source_file),
        "source_length": len(source_text),
        "content_preview": source_text[:500],
    }


@router.get("/{file_id}")
def get_file(
    file_id: str,
    db: Session = Depends(get_db),
):
    file_record = db.get(FileRecord, file_id)

    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")

    return {
        "status": "ok",
        "file": file_to_dict(file_record),
    }


@router.get("/{file_id}/content")
def read_local_file_content(
    file_id: str,
    db: Session = Depends(get_db),
):
    file_record = db.get(FileRecord, file_id)

    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")

    if not file_record.local_path:
        raise HTTPException(status_code=400, detail="File has no local_path. Please download it first.")

    path = Path(file_record.local_path)

    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Local file not found: {file_record.local_path}")

    content = path.read_text(encoding="utf-8")

    return {
        "status": "ok",
        "file": file_to_dict(file_record),
        "content_length": len(content),
        "content": content,
    }
