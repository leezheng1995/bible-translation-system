from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import AuditLog, Job, Segment, VectorChunk
from app.services.rag_context_builder import (
    build_rag_context,
    build_rag_context_text,
    save_rag_context_to_storage,
)


router = APIRouter(
    prefix="/rag",
    tags=["rag"],
)


class BuildRagContextRequest(BaseModel):
    top_k: int = 5
    save_to_file: bool = True


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


@router.get("/health")
def rag_health(db: Session = Depends(get_db)):
    vector_count = db.execute(select(VectorChunk)).scalars().all()

    return {
        "status": "ok",
        "vector_chunks": len(vector_count),
    }


@router.post("/segment/{segment_id}/context")
def build_segment_rag_context(
    segment_id: str,
    request: BuildRagContextRequest | None = None,
    db: Session = Depends(get_db),
):
    segment = db.get(Segment, segment_id)

    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")

    job = db.get(Job, segment.job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    top_k = request.top_k if request else 5
    save_to_file = request.save_to_file if request else True

    context = build_rag_context(
        db=db,
        segment=segment,
        top_k=top_k,
    )

    paths = None

    if save_to_file:
        paths = save_rag_context_to_storage(
            job_id=segment.job_id,
            segment_index=segment.segment_index,
            context=context,
        )

    job.current_stage = "rag_context_built"
    job.updated_at = datetime.utcnow()

    add_audit_log(
        db=db,
        job_id=job.id,
        event_type="rag_context_built",
        stage="rag_context_built",
        message=f"RAG context built for segment {segment.id}",
        payload_json=str(paths),
    )

    db.commit()
    db.refresh(job)

    return {
        "status": "ok",
        "job_id": job.id,
        "job_status": job.status,
        "current_stage": job.current_stage,
        "segment_id": segment.id,
        "segment_index": segment.segment_index,
        "paths": paths,
        "summary": context["summary"],
        "context": context,
        "context_text_preview": build_rag_context_text(context)[:1500],
    }


@router.post("/job/{job_id}/contexts")
def build_job_rag_contexts(
    job_id: str,
    request: BuildRagContextRequest | None = None,
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

    if not segments:
        raise HTTPException(status_code=400, detail="No segments found. Please run segmentation first.")

    top_k = request.top_k if request else 5
    save_to_file = request.save_to_file if request else True

    results = []

    for segment in segments:
        context = build_rag_context(
            db=db,
            segment=segment,
            top_k=top_k,
        )

        paths = None

        if save_to_file:
            paths = save_rag_context_to_storage(
                job_id=segment.job_id,
                segment_index=segment.segment_index,
                context=context,
            )

        results.append(
            {
                "segment_id": segment.id,
                "segment_index": segment.segment_index,
                "paths": paths,
                "summary": context["summary"],
            }
        )

    job.current_stage = "rag_contexts_built"
    job.updated_at = datetime.utcnow()

    add_audit_log(
        db=db,
        job_id=job.id,
        event_type="job_rag_contexts_built",
        stage="rag_contexts_built",
        message=f"RAG contexts built for {len(results)} segment(s).",
    )

    db.commit()
    db.refresh(job)

    return {
        "status": "ok",
        "job_id": job.id,
        "job_status": job.status,
        "current_stage": job.current_stage,
        "count": len(results),
        "contexts": results,
    }


@router.get("/job/{job_id}/files")
def list_rag_context_files(job_id: str):
    context_dir = Path("/app/storage") / "jobs" / job_id / "rag_contexts"

    if not context_dir.exists():
        return {
            "status": "ok",
            "job_id": job_id,
            "count": 0,
            "files": [],
        }

    files = sorted(context_dir.glob("*"))

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
def read_rag_context_file(path: str):
    context_path = Path(path)

    if not context_path.exists():
        raise HTTPException(status_code=404, detail=f"RAG context file not found: {path}")

    content = context_path.read_text(encoding="utf-8")

    return {
        "status": "ok",
        "path": str(context_path),
        "content_length": len(content),
        "content": content,
    }
