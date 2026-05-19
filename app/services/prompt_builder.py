from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import GlossaryTerm, Note, Rule, Segment


@dataclass
class PromptContext:
    segment: Segment
    glossary_terms: list[GlossaryTerm]
    rules: list[Rule]
    job_notes: list[Note]
    segment_notes: list[Note]


def _contains_term(source_text: str, term: str) -> bool:
    return term.lower() in source_text.lower()


def load_prompt_context(
    db: Session,
    segment: Segment,
) -> PromptContext:
    source_text = segment.source_text or ""

    all_glossary_terms = db.execute(
        select(GlossaryTerm)
        .where(GlossaryTerm.is_active == True)
        .order_by(GlossaryTerm.priority.asc(), GlossaryTerm.term.asc())
    ).scalars().all()

    matched_glossary_terms = [
        item for item in all_glossary_terms
        if _contains_term(source_text, item.term)
    ]

    rules = db.execute(
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

    return PromptContext(
        segment=segment,
        glossary_terms=matched_glossary_terms,
        rules=rules,
        job_notes=job_notes,
        segment_notes=segment_notes,
    )


def build_translation_prompt(context: PromptContext) -> str:
    segment = context.segment

    glossary_text = "\n".join(
        [
            f"- {item.term} => {item.translation}"
            + (f" | note: {item.note}" if item.note else "")
            for item in context.glossary_terms
        ]
    ) or "- No matched glossary terms."

    rules_text = "\n".join(
        [
            f"- [{item.rule_type}] {item.name}: {item.content}"
            for item in context.rules
        ]
    ) or "- No active rules."

    job_notes_text = "\n".join(
        [
            f"- {item.content}"
            for item in context.job_notes
        ]
    ) or "- No job-level notes."

    segment_notes_text = "\n".join(
        [
            f"- {item.content}"
            for item in context.segment_notes
        ]
    ) or "- No segment-level notes."

    verse_info_parts = []

    if segment.book:
        verse_info_parts.append(f"book={segment.book}")
    if segment.chapter:
        verse_info_parts.append(f"chapter={segment.chapter}")
    if segment.verse_start:
        verse_info_parts.append(f"verse_start={segment.verse_start}")
    if segment.verse_end:
        verse_info_parts.append(f"verse_end={segment.verse_end}")

    verse_info = ", ".join(verse_info_parts) if verse_info_parts else "not specified"

    prompt = f"""You are a professional Bible translation assistant.

Your task is to translate the source text into formal, faithful, clear Traditional Chinese.

Important principles:
1. Preserve the meaning of the source text.
2. Do not add theological interpretation that is not present in the source.
3. Use the glossary terms when applicable.
4. Follow the translation rules.
5. Consider human notes carefully.
6. Output only valid JSON. Do not include markdown.

Segment metadata:
- segment_id: {segment.id}
- segment_index: {segment.segment_index}
- verse_info: {verse_info}

Source text:
{segment.source_text}

Matched glossary:
{glossary_text}

Translation rules:
{rules_text}

Job-level notes:
{job_notes_text}

Segment-level notes:
{segment_notes_text}

Return JSON format:
{{
  "segment_id": "{segment.id}",
  "source_text": "{segment.source_text}",
  "translation": "<Traditional Chinese translation>",
  "glossary_used": [
    {{
      "term": "<source term>",
      "translation": "<chosen translation>"
    }}
  ],
  "notes": "<brief explanation in Traditional Chinese>"
}}
"""
    return prompt.strip()


def save_prompt_to_storage(
    job_id: str,
    segment_index: int,
    prompt: str,
    storage_root: str = "/app/storage",
) -> str:
    prompt_dir = Path(storage_root) / "jobs" / job_id / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)

    prompt_path = prompt_dir / f"segment_{segment_index:04d}_translation_prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")

    return str(prompt_path)
