import json
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import GlossaryTerm, Note, Rule, Segment, VectorChunk
from app.services.embedding_client import OllamaEmbeddingClient
from app.services.vector_store import cosine_similarity, deserialize_embedding


def contains_term(source_text: str, term: str) -> bool:
    return term.lower() in source_text.lower()


def glossary_to_dict(item: GlossaryTerm) -> dict[str, Any]:
    return {
        "id": item.id,
        "term": item.term,
        "translation": item.translation,
        "source_language": item.source_language,
        "target_language": item.target_language,
        "category": item.category,
        "priority": item.priority,
        "scope": item.scope,
        "note": item.note,
        "version": item.version,
    }


def rule_to_dict(item: Rule) -> dict[str, Any]:
    return {
        "id": item.id,
        "name": item.name,
        "rule_type": item.rule_type,
        "content": item.content,
        "scope": item.scope,
        "priority": item.priority,
        "version": item.version,
    }


def note_to_dict(item: Note) -> dict[str, Any]:
    return {
        "id": item.id,
        "job_id": item.job_id,
        "segment_id": item.segment_id,
        "note_type": item.note_type,
        "content": item.content,
        "priority": item.priority,
        "status": item.status,
    }


def segment_to_dict(item: Segment) -> dict[str, Any]:
    return {
        "id": item.id,
        "job_id": item.job_id,
        "file_id": item.file_id,
        "book": item.book,
        "chapter": item.chapter,
        "verse_start": item.verse_start,
        "verse_end": item.verse_end,
        "segment_index": item.segment_index,
        "source_text": item.source_text,
        "translated_text": item.translated_text,
        "status": item.status,
    }


def vector_chunk_to_context_dict(chunk: VectorChunk, score: float) -> dict[str, Any]:
    return {
        "id": chunk.id,
        "source_type": chunk.source_type,
        "source_id": chunk.source_id,
        "job_id": chunk.job_id,
        "segment_id": chunk.segment_id,
        "content": chunk.content,
        "metadata": json.loads(chunk.metadata_json or "{}"),
        "score": score,
    }


def search_relevant_vector_chunks(
    db: Session,
    query: str,
    job_id: str,
    top_k: int = 5,
    source_types: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    client = OllamaEmbeddingClient()
    query_embedding = client.embed_text(query)

    chunks = db.execute(
        select(VectorChunk)
        .where(VectorChunk.embedding_model == client.embedding_model)
        .order_by(VectorChunk.created_at.asc())
    ).scalars().all()

    scored = []

    for chunk in chunks:
        if source_types and chunk.source_type not in source_types:
            continue

        if chunk.job_id is not None and chunk.job_id != job_id:
            continue

        embedding = deserialize_embedding(chunk.embedding_json)
        score = cosine_similarity(query_embedding, embedding)
        scored.append((score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)

    return [
        vector_chunk_to_context_dict(chunk, score)
        for score, chunk in scored[:top_k]
    ]


def build_rag_context(
    db: Session,
    segment: Segment,
    top_k: int = 5,
) -> dict[str, Any]:
    source_text = segment.source_text or ""

    all_glossary_terms = db.execute(
        select(GlossaryTerm)
        .where(GlossaryTerm.is_active == True)
        .order_by(GlossaryTerm.priority.asc(), GlossaryTerm.term.asc())
    ).scalars().all()

    matched_glossary = [
        item for item in all_glossary_terms
        if contains_term(source_text, item.term)
    ]

    active_rules = db.execute(
        select(Rule)
        .where(Rule.is_active == True)
        .order_by(Rule.priority.asc(), Rule.name.asc())
    ).scalars().all()

    job_notes = db.execute(
        select(Note)
        .where(
            Note.job_id == segment.job_id,
            Note.segment_id == None,
            Note.status == "active",
        )
        .order_by(Note.priority.asc(), Note.created_at.desc())
    ).scalars().all()

    segment_notes = db.execute(
        select(Note)
        .where(
            Note.segment_id == segment.id,
            Note.status == "active",
        )
        .order_by(Note.priority.asc(), Note.created_at.desc())
    ).scalars().all()

    vector_results = search_relevant_vector_chunks(
        db=db,
        query=source_text,
        job_id=segment.job_id,
        top_k=top_k,
    )

    return {
        "segment": segment_to_dict(segment),
        "matched_glossary": [glossary_to_dict(item) for item in matched_glossary],
        "active_rules": [rule_to_dict(item) for item in active_rules],
        "job_notes": [note_to_dict(item) for item in job_notes],
        "segment_notes": [note_to_dict(item) for item in segment_notes],
        "vector_results": vector_results,
        "summary": {
            "matched_glossary_count": len(matched_glossary),
            "rules_count": len(active_rules),
            "job_notes_count": len(job_notes),
            "segment_notes_count": len(segment_notes),
            "vector_results_count": len(vector_results),
        },
    }


def build_rag_context_text(context: dict[str, Any]) -> str:
    segment = context["segment"]

    glossary_lines = []
    for item in context["matched_glossary"]:
        line = f"- {item['term']} => {item['translation']}"
        if item.get("note"):
            line += f" | note: {item['note']}"
        glossary_lines.append(line)

    rule_lines = []
    for item in context["active_rules"]:
        rule_lines.append(f"- [{item['rule_type']}] {item['name']}: {item['content']}")

    job_note_lines = []
    for item in context["job_notes"]:
        job_note_lines.append(f"- {item['content']}")

    segment_note_lines = []
    for item in context["segment_notes"]:
        segment_note_lines.append(f"- {item['content']}")

    vector_lines = []
    for item in context["vector_results"]:
        vector_lines.append(
            f"- score={item['score']:.4f} | {item['source_type']} | {item['content']}"
        )

    text = f"""RAG Context for Bible Translation

Segment:
- segment_id: {segment['id']}
- job_id: {segment['job_id']}
- segment_index: {segment['segment_index']}
- source_text: {segment['source_text']}

Matched Glossary:
{chr(10).join(glossary_lines) if glossary_lines else "- None"}

Active Rules:
{chr(10).join(rule_lines) if rule_lines else "- None"}

Job Notes:
{chr(10).join(job_note_lines) if job_note_lines else "- None"}

Segment Notes:
{chr(10).join(segment_note_lines) if segment_note_lines else "- None"}

Vector Retrieval Results:
{chr(10).join(vector_lines) if vector_lines else "- None"}
"""
    return text.strip()


def save_rag_context_to_storage(
    job_id: str,
    segment_index: int,
    context: dict[str, Any],
    storage_root: str = "/app/storage",
) -> dict[str, str]:
    context_dir = Path(storage_root) / "jobs" / job_id / "rag_contexts"
    context_dir.mkdir(parents=True, exist_ok=True)

    json_path = context_dir / f"segment_{segment_index:04d}_rag_context.json"
    txt_path = context_dir / f"segment_{segment_index:04d}_rag_context.txt"

    json_path.write_text(
        json.dumps(context, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    txt_path.write_text(
        build_rag_context_text(context),
        encoding="utf-8",
    )

    return {
        "json_path": str(json_path),
        "txt_path": str(txt_path),
    }
