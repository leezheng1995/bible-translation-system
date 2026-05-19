import json
import math
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import VectorChunk


def serialize_embedding(embedding: list[float]) -> str:
    return json.dumps(embedding)


def deserialize_embedding(raw: str) -> list[float]:
    return [float(x) for x in json.loads(raw)]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)


def upsert_vector_chunk(
    db: Session,
    source_type: str,
    source_id: str,
    content: str,
    embedding: list[float],
    embedding_model: str,
    job_id: str | None = None,
    segment_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> VectorChunk:
    existing = db.execute(
        select(VectorChunk).where(
            VectorChunk.source_type == source_type,
            VectorChunk.source_id == source_id,
            VectorChunk.embedding_model == embedding_model,
        )
    ).scalar_one_or_none()

    metadata_json = json.dumps(metadata or {}, ensure_ascii=False)

    if existing:
        existing.content = content
        existing.embedding_json = serialize_embedding(embedding)
        existing.job_id = job_id
        existing.segment_id = segment_id
        existing.metadata_json = metadata_json
        return existing

    chunk = VectorChunk(
        source_type=source_type,
        source_id=source_id,
        job_id=job_id,
        segment_id=segment_id,
        content=content,
        metadata_json=metadata_json,
        embedding_model=embedding_model,
        embedding_json=serialize_embedding(embedding),
    )

    db.add(chunk)
    return chunk


def vector_chunk_to_dict(chunk: VectorChunk, score: float | None = None) -> dict[str, Any]:
    data = {
        "id": chunk.id,
        "source_type": chunk.source_type,
        "source_id": chunk.source_id,
        "job_id": chunk.job_id,
        "segment_id": chunk.segment_id,
        "content": chunk.content,
        "metadata": json.loads(chunk.metadata_json or "{}"),
        "embedding_model": chunk.embedding_model,
        "created_at": chunk.created_at.isoformat() if chunk.created_at else None,
        "updated_at": chunk.updated_at.isoformat() if chunk.updated_at else None,
    }

    if score is not None:
        data["score"] = score

    return data
