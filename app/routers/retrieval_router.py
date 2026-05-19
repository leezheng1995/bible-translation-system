from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import AuditLog, GlossaryTerm, Job, Note, Rule, Segment, VectorChunk
from app.services.embedding_client import OllamaEmbeddingClient
from app.services.vector_store import (
    cosine_similarity,
    deserialize_embedding,
    upsert_vector_chunk,
    vector_chunk_to_dict,
)


router = APIRouter(
    prefix="/retrieval",
    tags=["retrieval"],
)


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = 5
    job_id: Optional[str] = None
    source_types: Optional[list[str]] = None


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
def retrieval_health():
    client = OllamaEmbeddingClient()
    embedding = client.embed_text("health check")

    return {
        "status": "ok",
        "embedding_model": client.embedding_model,
        "embedding_dimension": len(embedding),
        "sample_values": embedding[:5],
    }


@router.post("/index/job/{job_id}")
def index_job_context(
    job_id: str,
    force: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    job = db.get(Job, job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    client = OllamaEmbeddingClient()
    model_name = client.embedding_model

    if force:
        db.execute(
            delete(VectorChunk).where(
                or_(
                    VectorChunk.job_id == job_id,
                    VectorChunk.source_type.in_(["glossary", "rule"]),
                )
            )
        )
        db.flush()

    indexed = []

    glossary_terms = db.execute(
        select(GlossaryTerm)
        .where(GlossaryTerm.is_active == True)
        .order_by(GlossaryTerm.priority.asc(), GlossaryTerm.term.asc())
    ).scalars().all()

    for item in glossary_terms:
        content = f"Glossary: {item.term} => {item.translation}"
        if item.note:
            content += f". Note: {item.note}"

        embedding = client.embed_text(content)

        chunk = upsert_vector_chunk(
            db=db,
            source_type="glossary",
            source_id=item.id,
            content=content,
            embedding=embedding,
            embedding_model=model_name,
            metadata={
                "term": item.term,
                "translation": item.translation,
                "category": item.category,
                "scope": item.scope,
                "priority": item.priority,
            },
        )

        indexed.append(chunk)

    rules = db.execute(
        select(Rule)
        .where(Rule.is_active == True)
        .order_by(Rule.priority.asc(), Rule.name.asc())
    ).scalars().all()

    for item in rules:
        content = f"Rule [{item.rule_type}] {item.name}: {item.content}"

        embedding = client.embed_text(content)

        chunk = upsert_vector_chunk(
            db=db,
            source_type="rule",
            source_id=item.id,
            content=content,
            embedding=embedding,
            embedding_model=model_name,
            metadata={
                "name": item.name,
                "rule_type": item.rule_type,
                "scope": item.scope,
                "priority": item.priority,
                "version": item.version,
            },
        )

        indexed.append(chunk)

    segments = db.execute(
        select(Segment)
        .where(Segment.job_id == job_id)
        .order_by(Segment.segment_index.asc())
    ).scalars().all()

    for item in segments:
        content = f"Segment {item.segment_index}: {item.source_text}"

        embedding = client.embed_text(content)

        chunk = upsert_vector_chunk(
            db=db,
            source_type="segment",
            source_id=item.id,
            job_id=job_id,
            segment_id=item.id,
            content=content,
            embedding=embedding,
            embedding_model=model_name,
            metadata={
                "segment_index": item.segment_index,
                "book": item.book,
                "chapter": item.chapter,
                "verse_start": item.verse_start,
                "verse_end": item.verse_end,
            },
        )

        indexed.append(chunk)

    notes = db.execute(
        select(Note)
        .where(
            Note.job_id == job_id,
            Note.status == "active",
        )
        .order_by(Note.priority.asc(), Note.created_at.desc())
    ).scalars().all()

    for item in notes:
        content = f"Note [{item.note_type}]: {item.content}"

        embedding = client.embed_text(content)

        chunk = upsert_vector_chunk(
            db=db,
            source_type="note",
            source_id=item.id,
            job_id=job_id,
            segment_id=item.segment_id,
            content=content,
            embedding=embedding,
            embedding_model=model_name,
            metadata={
                "note_type": item.note_type,
                "priority": item.priority,
                "status": item.status,
            },
        )

        indexed.append(chunk)

    job.current_stage = "vector_indexed"
    job.updated_at = datetime.utcnow()

    add_audit_log(
        db=db,
        job_id=job.id,
        event_type="vector_index_built",
        stage="vector_indexed",
        message=f"Vector index built with {len(indexed)} chunk(s).",
    )

    db.commit()

    for chunk in indexed:
        db.refresh(chunk)

    db.refresh(job)

    return {
        "status": "ok",
        "job_id": job.id,
        "job_status": job.status,
        "current_stage": job.current_stage,
        "embedding_model": model_name,
        "indexed_count": len(indexed),
        "chunks": [vector_chunk_to_dict(chunk) for chunk in indexed],
    }


@router.post("/search")
def search_vector_chunks(
    request: SearchRequest,
    db: Session = Depends(get_db),
):
    client = OllamaEmbeddingClient()
    query_embedding = client.embed_text(request.query)

    chunks = db.execute(
        select(VectorChunk)
        .where(VectorChunk.embedding_model == client.embedding_model)
        .order_by(VectorChunk.created_at.asc())
    ).scalars().all()

    scored = []

    for chunk in chunks:
        if request.source_types and chunk.source_type not in request.source_types:
            continue

        if request.job_id:
            if chunk.job_id not in [None, request.job_id]:
                continue

        embedding = deserialize_embedding(chunk.embedding_json)
        score = cosine_similarity(query_embedding, embedding)
        scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)

    top_items = scored[: request.top_k]

    return {
        "status": "ok",
        "query": request.query,
        "embedding_model": client.embedding_model,
        "total_candidates": len(scored),
        "top_k": request.top_k,
        "results": [
            vector_chunk_to_dict(chunk, score=score)
            for score, chunk in top_items
        ],
    }


@router.get("/chunks")
def list_vector_chunks(
    job_id: Optional[str] = Query(default=None),
    source_type: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    stmt = select(VectorChunk)

    if job_id:
        stmt = stmt.where(VectorChunk.job_id == job_id)

    if source_type:
        stmt = stmt.where(VectorChunk.source_type == source_type)

    stmt = stmt.order_by(VectorChunk.created_at.asc()).limit(limit)

    chunks = db.execute(stmt).scalars().all()

    return {
        "status": "ok",
        "count": len(chunks),
        "chunks": [vector_chunk_to_dict(chunk) for chunk in chunks],
    }


@router.delete("/chunks")
def delete_vector_chunks(
    job_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    if job_id:
        db.execute(delete(VectorChunk).where(VectorChunk.job_id == job_id))
    else:
        db.execute(delete(VectorChunk))

    db.commit()

    return {
        "status": "ok",
        "message": "Vector chunks deleted",
        "job_id": job_id,
    }
