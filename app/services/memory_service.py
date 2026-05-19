import json
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    HumanReview,
    Job,
    Memory,
    Segment,
    TranslationVersion,
    VectorChunk,
)
from app.services.embedding_client import OllamaEmbeddingClient
from app.services.vector_store import (
    cosine_similarity,
    deserialize_embedding,
    upsert_vector_chunk,
    vector_chunk_to_dict,
)


MEMORY_SOURCE_TYPE = "human_approved_translation"


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


def parse_json_safe(raw: Optional[str]) -> dict[str, Any]:
    if not raw:
        return {}

    try:
        return json.loads(raw)
    except Exception:
        return {}


def memory_to_dict(item: Memory) -> dict[str, Any]:
    return {
        "id": item.id,
        "source_type": item.source_type,
        "source_id": item.source_id,
        "content": item.content,
        "category": item.category,
        "scope": item.scope,
        "embedding_model": item.embedding_model,
        "vector_id": item.vector_id,
        "approved_by": item.approved_by,
        "is_active": item.is_active,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def translation_version_to_dict(item: TranslationVersion) -> dict[str, Any]:
    return {
        "id": item.id,
        "job_id": item.job_id,
        "segment_id": item.segment_id,
        "version_no": item.version_no,
        "model_name": item.model_name,
        "prompt_version": item.prompt_version,
        "source_text": item.source_text,
        "translated_text": item.translated_text,
        "status": item.status,
        "qa_summary": item.qa_summary,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def human_review_to_dict(item: Optional[HumanReview]) -> Optional[dict[str, Any]]:
    if not item:
        return None

    return {
        "id": item.id,
        "job_id": item.job_id,
        "segment_id": item.segment_id,
        "version_id": item.version_id,
        "reviewer": item.reviewer,
        "decision": item.decision,
        "human_notes": item.human_notes,
        "revised_text": item.revised_text,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def segment_to_dict(item: Segment) -> dict[str, Any]:
    return {
        "id": item.id,
        "job_id": item.job_id,
        "segment_index": item.segment_index,
        "source_text": item.source_text,
        "translated_text": item.translated_text,
        "status": item.status,
    }


def get_latest_human_review(
    db: Session,
    segment_id: str,
) -> Optional[HumanReview]:
    return db.execute(
        select(HumanReview)
        .where(HumanReview.segment_id == segment_id)
        .order_by(HumanReview.created_at.desc())
        .limit(1)
    ).scalars().first()


def get_human_approved_versions(
    db: Session,
    job_id: str,
) -> list[TranslationVersion]:
    versions = db.execute(
        select(TranslationVersion)
        .where(
            TranslationVersion.job_id == job_id,
            TranslationVersion.status == "human_approved",
        )
        .order_by(TranslationVersion.segment_id.asc(), TranslationVersion.version_no.desc())
    ).scalars().all()

    latest_by_segment = {}

    for version in versions:
        current = latest_by_segment.get(version.segment_id)

        if current is None or version.version_no > current.version_no:
            latest_by_segment[version.segment_id] = version

    return list(latest_by_segment.values())


def build_memory_content(
    segment: Segment,
    version: TranslationVersion,
    human_review: Optional[HumanReview],
) -> str:
    qa = parse_json_safe(version.qa_summary)

    decision = human_review.decision if human_review else qa.get("decision", "human_approved")
    reviewer = human_review.reviewer if human_review else qa.get("reviewer", "human")
    human_notes = human_review.human_notes if human_review else qa.get("human_notes")

    lines = [
        "Human Approved Bible Translation Memory",
        "",
        f"Source text: {segment.source_text}",
        f"Approved Traditional Chinese translation: {version.translated_text}",
        f"Decision: {decision}",
        f"Reviewer: {reviewer}",
    ]

    if human_notes:
        lines.append(f"Human notes: {human_notes}")

    lines.extend(
        [
            "",
            "Memory usage policy:",
            "- Use this as an approved precedent for future Bible translation.",
            "- Prioritize the approved wording and style when similar source text appears.",
            "- This memory is allowed because it was approved or revised by a human reviewer.",
        ]
    )

    return "\n".join(lines)


def list_memory_candidates(
    db: Session,
    job_id: str,
) -> dict[str, Any]:
    job = db.get(Job, job_id)

    if not job:
        raise ValueError(f"Job not found: {job_id}")

    versions = get_human_approved_versions(db, job_id)

    candidates = []

    for version in versions:
        segment = db.get(Segment, version.segment_id)

        if not segment:
            continue

        human_review = get_latest_human_review(db, segment.id)

        existing_memory = db.execute(
            select(Memory)
            .where(
                Memory.source_type == MEMORY_SOURCE_TYPE,
                Memory.source_id == version.id,
                Memory.is_active == True,
            )
        ).scalars().first()

        candidates.append(
            {
                "eligible": True,
                "reason": "translation_version.status is human_approved",
                "already_has_memory": existing_memory is not None,
                "segment": segment_to_dict(segment),
                "translation_version": translation_version_to_dict(version),
                "human_review": human_review_to_dict(human_review),
            }
        )

    return {
        "status": "ok",
        "job_id": job.id,
        "job_status": job.status,
        "current_stage": job.current_stage,
        "count": len(candidates),
        "candidates": candidates,
    }


def build_job_memories(
    db: Session,
    job_id: str,
    force: bool = False,
) -> dict[str, Any]:
    job = db.get(Job, job_id)

    if not job:
        raise ValueError(f"Job not found: {job_id}")

    versions = get_human_approved_versions(db, job_id)

    if not versions:
        raise ValueError("No human_approved translation versions found. Please complete Day 20 human review first.")

    client = OllamaEmbeddingClient()

    created = []
    skipped = []

    for version in versions:
        segment = db.get(Segment, version.segment_id)

        if not segment:
            skipped.append(
                {
                    "version_id": version.id,
                    "reason": "segment not found",
                }
            )
            continue

        existing_memories = db.execute(
            select(Memory)
            .where(
                Memory.source_type == MEMORY_SOURCE_TYPE,
                Memory.source_id == version.id,
                Memory.is_active == True,
            )
        ).scalars().all()

        if existing_memories and not force:
            skipped.append(
                {
                    "version_id": version.id,
                    "reason": "memory already exists",
                    "memories": [memory_to_dict(item) for item in existing_memories],
                }
            )
            continue

        if existing_memories and force:
            for old_memory in existing_memories:
                db.execute(
                    delete(VectorChunk).where(
                        VectorChunk.source_type == "memory",
                        VectorChunk.source_id == old_memory.id,
                    )
                )
                old_memory.is_active = False

            db.flush()

        human_review = get_latest_human_review(db, segment.id)
        content = build_memory_content(
            segment=segment,
            version=version,
            human_review=human_review,
        )

        embedding = client.embed_text(content)

        reviewer = None

        if human_review and human_review.reviewer:
            reviewer = human_review.reviewer
        else:
            reviewer = parse_json_safe(version.qa_summary).get("reviewer", "human")

        memory = Memory(
            source_type=MEMORY_SOURCE_TYPE,
            source_id=version.id,
            content=content,
            category="approved_translation",
            scope=f"job:{job.id};segment:{segment.id};segment_index:{segment.segment_index}",
            embedding_model=client.embedding_model,
            vector_id=None,
            approved_by=reviewer,
            is_active=True,
        )

        db.add(memory)
        db.flush()

        chunk = upsert_vector_chunk(
            db=db,
            source_type="memory",
            source_id=memory.id,
            job_id=job.id,
            segment_id=segment.id,
            content=content,
            embedding=embedding,
            embedding_model=client.embedding_model,
            metadata={
                "memory_id": memory.id,
                "translation_version_id": version.id,
                "segment_id": segment.id,
                "segment_index": segment.segment_index,
                "approved_by": reviewer,
                "category": "approved_translation",
                "write_policy": "human_approved_only",
            },
        )

        db.flush()

        memory.vector_id = chunk.id

        created.append(
            {
                "memory": memory_to_dict(memory),
                "vector_chunk": vector_chunk_to_dict(chunk),
            }
        )

    job.current_stage = "memory_built"
    job.updated_at = datetime.utcnow()

    add_audit_log(
        db=db,
        job_id=job.id,
        event_type="memory_built",
        stage="memory_built",
        message=f"Memory builder completed. created={len(created)}, skipped={len(skipped)}",
        payload_json=json.dumps(
            {
                "created_count": len(created),
                "skipped_count": len(skipped),
                "write_policy": "human_approved_only",
            },
            ensure_ascii=False,
        ),
    )

    db.commit()

    return {
        "status": "ok",
        "job_id": job.id,
        "job_status": job.status,
        "current_stage": job.current_stage,
        "write_policy": "human_approved_only",
        "created_count": len(created),
        "skipped_count": len(skipped),
        "created": created,
        "skipped": skipped,
    }


def list_job_memories(
    db: Session,
    job_id: str,
) -> dict[str, Any]:
    job = db.get(Job, job_id)

    if not job:
        raise ValueError(f"Job not found: {job_id}")

    chunks = db.execute(
        select(VectorChunk)
        .where(
            VectorChunk.job_id == job_id,
            VectorChunk.source_type == "memory",
        )
        .order_by(VectorChunk.created_at.asc())
    ).scalars().all()

    memories = []

    for chunk in chunks:
        memory = db.get(Memory, chunk.source_id)

        if not memory or not memory.is_active:
            continue

        memories.append(
            {
                "memory": memory_to_dict(memory),
                "vector_chunk": vector_chunk_to_dict(chunk),
            }
        )

    return {
        "status": "ok",
        "job_id": job.id,
        "job_status": job.status,
        "current_stage": job.current_stage,
        "count": len(memories),
        "memories": memories,
    }


def search_memories(
    db: Session,
    query: str,
    top_k: int = 5,
) -> dict[str, Any]:
    client = OllamaEmbeddingClient()
    query_embedding = client.embed_text(query)

    chunks = db.execute(
        select(VectorChunk)
        .where(
            VectorChunk.source_type == "memory",
            VectorChunk.embedding_model == client.embedding_model,
        )
        .order_by(VectorChunk.created_at.asc())
    ).scalars().all()

    scored = []

    for chunk in chunks:
        embedding = deserialize_embedding(chunk.embedding_json)
        score = cosine_similarity(query_embedding, embedding)
        scored.append((score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)

    results = []

    for score, chunk in scored[:top_k]:
        memory = db.get(Memory, chunk.source_id)

        if not memory or not memory.is_active:
            continue

        results.append(
            {
                "score": score,
                "memory": memory_to_dict(memory),
                "vector_chunk": vector_chunk_to_dict(chunk, score=score),
            }
        )

    return {
        "status": "ok",
        "query": query,
        "embedding_model": client.embedding_model,
        "top_k": top_k,
        "count": len(results),
        "results": results,
    }
