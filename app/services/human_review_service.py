import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    HumanReview,
    Job,
    Review,
    Segment,
    TranslationVersion,
)


VALID_DECISIONS = {
    "approved",
    "revised",
    "rejected",
    "revision_requested",
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


def get_latest_translation_version(
    db: Session,
    segment_id: str,
) -> Optional[TranslationVersion]:
    return db.execute(
        select(TranslationVersion)
        .where(TranslationVersion.segment_id == segment_id)
        .order_by(TranslationVersion.version_no.desc())
        .limit(1)
    ).scalars().first()


def get_next_version_no(
    db: Session,
    job_id: str,
    segment_id: str,
) -> int:
    latest = db.execute(
        select(TranslationVersion)
        .where(
            TranslationVersion.job_id == job_id,
            TranslationVersion.segment_id == segment_id,
        )
        .order_by(TranslationVersion.version_no.desc())
        .limit(1)
    ).scalars().first()

    if not latest:
        return 1

    return latest.version_no + 1


def human_review_to_dict(item: HumanReview) -> dict[str, Any]:
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
        "qa_summary": item.qa_summary,
        "status": item.status,
        "created_at": item.created_at.isoformat() if item.created_at else None,
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
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def review_to_dict(item: Review) -> dict[str, Any]:
    return {
        "id": item.id,
        "job_id": item.job_id,
        "segment_id": item.segment_id,
        "version_id": item.version_id,
        "model_name": item.model_name,
        "review_type": item.review_type,
        "score": item.score,
        "issues_json": item.issues_json,
        "suggestions": item.suggestions,
        "status": item.status,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def save_human_review_artifact(
    job_id: str,
    segment_index: int,
    payload: dict[str, Any],
) -> str:
    output_dir = Path("/app/storage") / "jobs" / job_id / "human_reviews"
    output_dir.mkdir(parents=True, exist_ok=True)

    path = output_dir / f"segment_{segment_index:04d}_human_review.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return str(path)


def build_review_package(
    db: Session,
    segment_id: str,
) -> dict[str, Any]:
    segment = db.get(Segment, segment_id)

    if not segment:
        raise ValueError(f"Segment not found: {segment_id}")

    job = db.get(Job, segment.job_id)

    if not job:
        raise ValueError(f"Job not found: {segment.job_id}")

    latest_version = get_latest_translation_version(db, segment.id)

    if not latest_version:
        raise ValueError("No translation version found for this segment.")

    ai_reviews = db.execute(
        select(Review)
        .where(
            Review.segment_id == segment.id,
            Review.version_id == latest_version.id,
        )
        .order_by(Review.created_at.asc())
    ).scalars().all()

    human_reviews = db.execute(
        select(HumanReview)
        .where(HumanReview.segment_id == segment.id)
        .order_by(HumanReview.created_at.desc())
    ).scalars().all()

    return {
        "job_id": job.id,
        "job_status": job.status,
        "current_stage": job.current_stage,
        "segment": segment_to_dict(segment),
        "latest_translation_version": translation_version_to_dict(latest_version),
        "ai_reviews_count": len(ai_reviews),
        "ai_reviews": [review_to_dict(item) for item in ai_reviews],
        "human_reviews_count": len(human_reviews),
        "human_reviews": [human_review_to_dict(item) for item in human_reviews],
    }


def submit_human_review(
    db: Session,
    segment_id: str,
    decision: str,
    reviewer: str = "human",
    human_notes: Optional[str] = None,
    revised_text: Optional[str] = None,
) -> dict[str, Any]:
    if decision not in VALID_DECISIONS:
        raise ValueError(f"Invalid decision: {decision}. Valid decisions: {sorted(VALID_DECISIONS)}")

    segment = db.get(Segment, segment_id)

    if not segment:
        raise ValueError(f"Segment not found: {segment_id}")

    job = db.get(Job, segment.job_id)

    if not job:
        raise ValueError(f"Job not found: {segment.job_id}")

    latest_version = get_latest_translation_version(db, segment.id)

    if not latest_version:
        raise ValueError("No translation version found for this segment.")

    final_revised_text = revised_text.strip() if revised_text else None

    if decision == "revised" and not final_revised_text:
        raise ValueError("revised_text is required when decision is revised.")

    human_review = HumanReview(
        job_id=job.id,
        segment_id=segment.id,
        version_id=latest_version.id,
        reviewer=reviewer,
        decision=decision,
        human_notes=human_notes,
        revised_text=final_revised_text,
    )

    db.add(human_review)
    db.flush()

    new_version = None

    if decision == "approved":
        latest_version.status = "human_approved"
        segment.status = "human_approved"
        job.current_stage = "human_approved"

    elif decision == "revised":
        version_no = get_next_version_no(
            db=db,
            job_id=job.id,
            segment_id=segment.id,
        )

        new_version = TranslationVersion(
            job_id=job.id,
            segment_id=segment.id,
            version_no=version_no,
            model_name="human_reviewer",
            prompt_version="human_revision",
            source_text=segment.source_text,
            translated_text=final_revised_text,
            qa_summary=json.dumps(
                {
                    "decision": decision,
                    "reviewer": reviewer,
                    "human_notes": human_notes,
                    "base_version_id": latest_version.id,
                },
                ensure_ascii=False,
            ),
            status="human_approved",
        )

        db.add(new_version)

        latest_version.status = "revised_by_human"
        segment.translated_text = final_revised_text
        segment.status = "human_revised"
        job.current_stage = "human_revised"

    elif decision == "revision_requested":
        latest_version.status = "revision_requested"
        segment.status = "revision_requested"
        job.current_stage = "revision_requested"

    elif decision == "rejected":
        latest_version.status = "human_rejected"
        segment.status = "human_rejected"
        job.current_stage = "human_rejected"

    segment.updated_at = datetime.utcnow()
    job.updated_at = datetime.utcnow()

    artifact_payload = {
        "human_review": human_review_to_dict(human_review),
        "decision": decision,
        "reviewer": reviewer,
        "human_notes": human_notes,
        "base_translation_version": translation_version_to_dict(latest_version),
        "new_translation_version": translation_version_to_dict(new_version) if new_version else None,
        "segment": segment_to_dict(segment),
    }

    artifact_path = save_human_review_artifact(
        job_id=job.id,
        segment_index=segment.segment_index,
        payload=artifact_payload,
    )

    add_audit_log(
        db=db,
        job_id=job.id,
        event_type="human_review_submitted",
        stage=job.current_stage,
        message=f"Human review submitted for segment {segment.id}: {decision}",
        payload_json=json.dumps(
            {
                "human_review_id": human_review.id,
                "artifact_path": artifact_path,
                "decision": decision,
            },
            ensure_ascii=False,
        ),
    )

    db.commit()

    db.refresh(human_review)
    db.refresh(segment)
    db.refresh(job)

    if new_version:
        db.refresh(new_version)

    if latest_version:
        db.refresh(latest_version)

    return {
        "status": "ok",
        "job_id": job.id,
        "job_status": job.status,
        "current_stage": job.current_stage,
        "segment": segment_to_dict(segment),
        "human_review": human_review_to_dict(human_review),
        "base_translation_version": translation_version_to_dict(latest_version),
        "new_translation_version": translation_version_to_dict(new_version) if new_version else None,
        "artifact_path": artifact_path,
    }
