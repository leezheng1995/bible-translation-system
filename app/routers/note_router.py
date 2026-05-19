from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import AuditLog, Job, Note, Segment


router = APIRouter(
    prefix="/notes",
    tags=["notes"],
)


class NoteCreateRequest(BaseModel):
    content: str = Field(..., min_length=1)
    job_id: Optional[str] = None
    segment_id: Optional[str] = None
    note_type: str = "human_note"
    priority: int = 5
    status: str = "active"


class NoteUpdateRequest(BaseModel):
    content: Optional[str] = None
    note_type: Optional[str] = None
    priority: Optional[int] = None
    status: Optional[str] = None


def note_to_dict(note: Note) -> dict:
    return {
        "id": note.id,
        "job_id": note.job_id,
        "segment_id": note.segment_id,
        "note_type": note.note_type,
        "content": note.content,
        "priority": note.priority,
        "status": note.status,
        "created_at": note.created_at.isoformat() if note.created_at else None,
        "updated_at": note.updated_at.isoformat() if note.updated_at else None,
    }


def add_audit_log(
    db: Session,
    event_type: str,
    stage: str,
    message: str,
    job_id: Optional[str] = None,
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


@router.post("")
def create_note(
    request: NoteCreateRequest,
    db: Session = Depends(get_db),
):
    if request.job_id:
        job = db.get(Job, request.job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

    if request.segment_id:
        segment = db.get(Segment, request.segment_id)
        if not segment:
            raise HTTPException(status_code=404, detail="Segment not found")

    note = Note(
        job_id=request.job_id,
        segment_id=request.segment_id,
        note_type=request.note_type,
        content=request.content.strip(),
        priority=request.priority,
        status=request.status,
    )

    db.add(note)

    add_audit_log(
        db=db,
        job_id=request.job_id,
        event_type="note_created",
        stage="notes",
        message=f"Note created: {request.note_type}",
    )

    db.commit()
    db.refresh(note)

    return {
        "status": "ok",
        "note": note_to_dict(note),
    }


@router.get("")
def list_notes(
    job_id: Optional[str] = Query(default=None),
    segment_id: Optional[str] = Query(default=None),
    note_type: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default="active"),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    stmt = select(Note)

    if job_id:
        stmt = stmt.where(Note.job_id == job_id)

    if segment_id:
        stmt = stmt.where(Note.segment_id == segment_id)

    if note_type:
        stmt = stmt.where(Note.note_type == note_type)

    if status:
        stmt = stmt.where(Note.status == status)

    stmt = stmt.order_by(Note.priority.asc(), Note.created_at.desc()).limit(limit)

    notes = db.execute(stmt).scalars().all()

    return {
        "count": len(notes),
        "notes": [note_to_dict(note) for note in notes],
    }


@router.get("/{note_id}")
def get_note(
    note_id: str,
    db: Session = Depends(get_db),
):
    note = db.get(Note, note_id)

    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    return {
        "status": "ok",
        "note": note_to_dict(note),
    }


@router.put("/{note_id}")
def update_note(
    note_id: str,
    request: NoteUpdateRequest,
    db: Session = Depends(get_db),
):
    note = db.get(Note, note_id)

    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    if request.content is not None:
        note.content = request.content.strip()
    if request.note_type is not None:
        note.note_type = request.note_type
    if request.priority is not None:
        note.priority = request.priority
    if request.status is not None:
        note.status = request.status

    note.updated_at = datetime.utcnow()

    add_audit_log(
        db=db,
        job_id=note.job_id,
        event_type="note_updated",
        stage="notes",
        message=f"Note updated: {note.id}",
    )

    db.commit()
    db.refresh(note)

    return {
        "status": "ok",
        "note": note_to_dict(note),
    }


@router.delete("/{note_id}")
def deactivate_note(
    note_id: str,
    db: Session = Depends(get_db),
):
    note = db.get(Note, note_id)

    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    note.status = "inactive"
    note.updated_at = datetime.utcnow()

    add_audit_log(
        db=db,
        job_id=note.job_id,
        event_type="note_deactivated",
        stage="notes",
        message=f"Note deactivated: {note.id}",
    )

    db.commit()
    db.refresh(note)

    return {
        "status": "ok",
        "note": note_to_dict(note),
    }
