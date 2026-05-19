from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import AuditLog, Job, Segment
from app.services.prompt_builder import (
    build_translation_prompt,
    load_prompt_context,
    save_prompt_to_storage,
)


router = APIRouter(
    prefix="/prompts",
    tags=["prompts"],
)


class BuildPromptRequest(BaseModel):
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


@router.post("/segment/{segment_id}/translation")
def build_segment_translation_prompt(
    segment_id: str,
    request: BuildPromptRequest | None = None,
    db: Session = Depends(get_db),
):
    segment = db.get(Segment, segment_id)

    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")

    job = db.get(Job, segment.job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    context = load_prompt_context(db=db, segment=segment)
    prompt = build_translation_prompt(context)

    save_to_file = True if request is None else request.save_to_file
    prompt_path = None

    if save_to_file:
        prompt_path = save_prompt_to_storage(
            job_id=segment.job_id,
            segment_index=segment.segment_index,
            prompt=prompt,
        )

    job.current_stage = "prompt_built"
    job.updated_at = datetime.utcnow()

    add_audit_log(
        db=db,
        job_id=job.id,
        event_type="translation_prompt_built",
        stage="prompt_built",
        message=f"Translation prompt built for segment {segment.id}",
        payload_json=prompt_path,
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
        "prompt_path": prompt_path,
        "prompt_length": len(prompt),
        "matched_glossary_count": len(context.glossary_terms),
        "rules_count": len(context.rules),
        "job_notes_count": len(context.job_notes),
        "segment_notes_count": len(context.segment_notes),
        "prompt": prompt,
    }


@router.post("/job/{job_id}/translation")
def build_job_translation_prompts(
    job_id: str,
    request: BuildPromptRequest | None = None,
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

    results = []

    for segment in segments:
        context = load_prompt_context(db=db, segment=segment)
        prompt = build_translation_prompt(context)

        save_to_file = True if request is None else request.save_to_file
        prompt_path = None

        if save_to_file:
            prompt_path = save_prompt_to_storage(
                job_id=segment.job_id,
                segment_index=segment.segment_index,
                prompt=prompt,
            )

        results.append(
            {
                "segment_id": segment.id,
                "segment_index": segment.segment_index,
                "prompt_path": prompt_path,
                "prompt_length": len(prompt),
                "matched_glossary_count": len(context.glossary_terms),
                "rules_count": len(context.rules),
                "job_notes_count": len(context.job_notes),
                "segment_notes_count": len(context.segment_notes),
            }
        )

    job.current_stage = "prompts_built"
    job.updated_at = datetime.utcnow()

    add_audit_log(
        db=db,
        job_id=job.id,
        event_type="job_translation_prompts_built",
        stage="prompts_built",
        message=f"Translation prompts built for {len(results)} segment(s).",
    )

    db.commit()
    db.refresh(job)

    return {
        "status": "ok",
        "job_id": job.id,
        "job_status": job.status,
        "current_stage": job.current_stage,
        "count": len(results),
        "prompts": results,
    }


@router.get("/job/{job_id}/files")
def list_prompt_files(
    job_id: str,
):
    prompt_dir = Path("/app/storage") / "jobs" / job_id / "prompts"

    if not prompt_dir.exists():
        return {
            "status": "ok",
            "job_id": job_id,
            "count": 0,
            "files": [],
        }

    files = sorted(prompt_dir.glob("*.txt"))

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
        ],
    }


@router.get("/file")
def read_prompt_file(
    path: str,
):
    prompt_path = Path(path)

    if not prompt_path.exists():
        raise HTTPException(status_code=404, detail=f"Prompt file not found: {path}")

    content = prompt_path.read_text(encoding="utf-8")

    return {
        "status": "ok",
        "path": str(prompt_path),
        "content_length": len(content),
        "content": content,
    }
