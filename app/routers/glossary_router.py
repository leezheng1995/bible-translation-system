from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import AuditLog, GlossaryTerm


router = APIRouter(
    prefix="/glossary",
    tags=["glossary"],
)


class GlossaryCreateRequest(BaseModel):
    term: str = Field(..., min_length=1)
    translation: str = Field(..., min_length=1)
    source_language: str = "en"
    target_language: str = "zh-TW"
    category: Optional[str] = None
    priority: int = 5
    scope: Optional[str] = None
    note: Optional[str] = None
    version: int = 1


class GlossaryUpdateRequest(BaseModel):
    translation: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[int] = None
    scope: Optional[str] = None
    note: Optional[str] = None
    is_active: Optional[bool] = None
    version: Optional[int] = None


def glossary_to_dict(item: GlossaryTerm) -> dict:
    return {
        "id": item.id,
        "term": item.term,
        "source_language": item.source_language,
        "target_language": item.target_language,
        "translation": item.translation,
        "category": item.category,
        "priority": item.priority,
        "scope": item.scope,
        "note": item.note,
        "is_active": item.is_active,
        "version": item.version,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
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
def create_glossary_term(
    request: GlossaryCreateRequest,
    db: Session = Depends(get_db),
):
    item = GlossaryTerm(
        term=request.term.strip(),
        translation=request.translation.strip(),
        source_language=request.source_language,
        target_language=request.target_language,
        category=request.category,
        priority=request.priority,
        scope=request.scope,
        note=request.note,
        version=request.version,
        is_active=True,
    )

    db.add(item)

    add_audit_log(
        db=db,
        event_type="glossary_created",
        stage="glossary",
        message=f"Glossary term created: {request.term} -> {request.translation}",
    )

    db.commit()
    db.refresh(item)

    return {
        "status": "ok",
        "glossary": glossary_to_dict(item),
    }


@router.get("")
def list_glossary_terms(
    q: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    active_only: bool = Query(default=True),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    stmt = select(GlossaryTerm)

    if active_only:
        stmt = stmt.where(GlossaryTerm.is_active == True)

    if q:
        like_q = f"%{q}%"
        stmt = stmt.where(
            (GlossaryTerm.term.like(like_q)) |
            (GlossaryTerm.translation.like(like_q)) |
            (GlossaryTerm.note.like(like_q))
        )

    if category:
        stmt = stmt.where(GlossaryTerm.category == category)

    stmt = stmt.order_by(GlossaryTerm.priority.asc(), GlossaryTerm.term.asc()).limit(limit)

    items = db.execute(stmt).scalars().all()

    return {
        "count": len(items),
        "glossary": [glossary_to_dict(item) for item in items],
    }


@router.get("/{glossary_id}")
def get_glossary_term(
    glossary_id: str,
    db: Session = Depends(get_db),
):
    item = db.get(GlossaryTerm, glossary_id)

    if not item:
        raise HTTPException(status_code=404, detail="Glossary term not found")

    return {
        "status": "ok",
        "glossary": glossary_to_dict(item),
    }


@router.put("/{glossary_id}")
def update_glossary_term(
    glossary_id: str,
    request: GlossaryUpdateRequest,
    db: Session = Depends(get_db),
):
    item = db.get(GlossaryTerm, glossary_id)

    if not item:
        raise HTTPException(status_code=404, detail="Glossary term not found")

    if request.translation is not None:
        item.translation = request.translation.strip()
    if request.category is not None:
        item.category = request.category
    if request.priority is not None:
        item.priority = request.priority
    if request.scope is not None:
        item.scope = request.scope
    if request.note is not None:
        item.note = request.note
    if request.is_active is not None:
        item.is_active = request.is_active
    if request.version is not None:
        item.version = request.version

    item.updated_at = datetime.utcnow()

    add_audit_log(
        db=db,
        event_type="glossary_updated",
        stage="glossary",
        message=f"Glossary term updated: {item.term}",
    )

    db.commit()
    db.refresh(item)

    return {
        "status": "ok",
        "glossary": glossary_to_dict(item),
    }


@router.delete("/{glossary_id}")
def deactivate_glossary_term(
    glossary_id: str,
    db: Session = Depends(get_db),
):
    item = db.get(GlossaryTerm, glossary_id)

    if not item:
        raise HTTPException(status_code=404, detail="Glossary term not found")

    item.is_active = False
    item.updated_at = datetime.utcnow()

    add_audit_log(
        db=db,
        event_type="glossary_deactivated",
        stage="glossary",
        message=f"Glossary term deactivated: {item.term}",
    )

    db.commit()
    db.refresh(item)

    return {
        "status": "ok",
        "glossary": glossary_to_dict(item),
    }
