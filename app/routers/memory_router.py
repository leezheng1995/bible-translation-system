from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Memory
from app.services.memory_service import (
    build_job_memories,
    list_job_memories,
    list_memory_candidates,
    memory_to_dict,
    search_memories,
)


router = APIRouter(
    prefix="/memory",
    tags=["memory"],
)


class BuildMemoryRequest(BaseModel):
    force: bool = False


class SearchMemoryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = 5


@router.get("/policy")
def memory_write_policy():
    return {
        "status": "ok",
        "policy_name": "human_approved_only",
        "rules": [
            "Only human_approved translation_versions can be written into memory.",
            "AI draft translations cannot be written into memory directly.",
            "AI review output cannot be written into memory directly.",
            "Human revised translations are allowed because the new version status is human_approved.",
            "Every memory must keep source_id pointing to the approved translation_version.",
        ],
    }


@router.get("")
def list_all_memories(
    active_only: bool = Query(default=True),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    stmt = select(Memory)

    if active_only:
        stmt = stmt.where(Memory.is_active == True)

    stmt = stmt.order_by(Memory.created_at.asc()).limit(limit)

    items = db.execute(stmt).scalars().all()

    return {
        "status": "ok",
        "count": len(items),
        "memories": [memory_to_dict(item) for item in items],
    }


@router.get("/job/{job_id}/candidates")
def get_memory_candidates(
    job_id: str,
    db: Session = Depends(get_db),
):
    try:
        return list_memory_candidates(
            db=db,
            job_id=job_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/job/{job_id}/build")
def build_memory_for_job(
    job_id: str,
    request: BuildMemoryRequest | None = None,
    db: Session = Depends(get_db),
):
    force = request.force if request else False

    try:
        return build_job_memories(
            db=db,
            job_id=job_id,
            force=force,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/job/{job_id}")
def get_job_memories(
    job_id: str,
    db: Session = Depends(get_db),
):
    try:
        return list_job_memories(
            db=db,
            job_id=job_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/search")
def search_memory(
    request: SearchMemoryRequest,
    db: Session = Depends(get_db),
):
    try:
        return search_memories(
            db=db,
            query=request.query,
            top_k=request.top_k,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
