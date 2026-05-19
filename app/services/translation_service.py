import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, ErrorLog, Job, Segment, TranslationVersion
from app.services.ollama_client import OllamaClient, extract_json_object, remove_thinking_text


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


def add_error_log(
    db: Session,
    job_id: Optional[str],
    stage: str,
    error_type: str,
    error_message: str,
    traceback: Optional[str] = None,
) -> None:
    db.add(
        ErrorLog(
            job_id=job_id,
            stage=stage,
            error_type=error_type,
            error_message=error_message,
            traceback=traceback,
        )
    )


def get_prompt_path(segment: Segment) -> Path:
    return (
        Path("/app/storage")
        / "jobs"
        / segment.job_id
        / "prompts"
        / f"segment_{segment.segment_index:04d}_translation_prompt.txt"
    )


def get_translation_dir(job_id: str) -> Path:
    path = Path("/app/storage") / "jobs" / job_id / "translations"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_translation_artifacts(
    job_id: str,
    segment_index: int,
    raw_response: str,
    cleaned_response: str,
    parsed_json: Optional[dict[str, Any]],
) -> dict[str, str]:
    output_dir = get_translation_dir(job_id)

    raw_path = output_dir / f"segment_{segment_index:04d}_translation_raw.txt"
    cleaned_path = output_dir / f"segment_{segment_index:04d}_translation_cleaned.txt"
    json_path = output_dir / f"segment_{segment_index:04d}_translation.json"

    raw_path.write_text(raw_response, encoding="utf-8")
    cleaned_path.write_text(cleaned_response, encoding="utf-8")

    json_payload = parsed_json if parsed_json is not None else {
        "json_extracted": False,
        "cleaned_response": cleaned_response,
    }

    json_path.write_text(
        json.dumps(json_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "raw_path": str(raw_path),
        "cleaned_path": str(cleaned_path),
        "json_path": str(json_path),
    }


def extract_translation_text(
    parsed_json: Optional[dict[str, Any]],
    cleaned_response: str,
) -> str:
    if parsed_json:
        value = parsed_json.get("translation")
        if isinstance(value, str) and value.strip():
            return value.strip()

    return cleaned_response.strip()


def translation_version_to_dict(version: TranslationVersion) -> dict[str, Any]:
    return {
        "id": version.id,
        "job_id": version.job_id,
        "segment_id": version.segment_id,
        "version_no": version.version_no,
        "model_name": version.model_name,
        "prompt_version": version.prompt_version,
        "source_text": version.source_text,
        "translated_text": version.translated_text,
        "qa_summary": version.qa_summary,
        "status": version.status,
        "created_at": version.created_at.isoformat() if version.created_at else None,
    }


def segment_to_dict(segment: Segment) -> dict[str, Any]:
    return {
        "id": segment.id,
        "job_id": segment.job_id,
        "segment_index": segment.segment_index,
        "source_text": segment.source_text,
        "translated_text": segment.translated_text,
        "status": segment.status,
        "updated_at": segment.updated_at.isoformat() if segment.updated_at else None,
    }


def get_next_version_no(
    db: Session,
    job_id: str,
    segment_id: str,
) -> int:
    versions = db.execute(
        select(TranslationVersion)
        .where(
            TranslationVersion.job_id == job_id,
            TranslationVersion.segment_id == segment_id,
        )
        .order_by(TranslationVersion.version_no.desc())
    ).scalars().all()

    if not versions:
        return 1

    return versions[0].version_no + 1


def translate_segment_sync(
    db: Session,
    segment_id: str,
    force: bool = False,
    timeout_seconds: int = 900,
) -> dict[str, Any]:
    segment = db.get(Segment, segment_id)

    if not segment:
        raise ValueError(f"Segment not found: {segment_id}")

    job = db.get(Job, segment.job_id)

    if not job:
        raise ValueError(f"Job not found: {segment.job_id}")

    if segment.translated_text and not force:
        return {
            "status": "ok",
            "skipped": True,
            "message": "Segment already translated. Use force=true to translate again.",
            "job_id": job.id,
            "segment": segment_to_dict(segment),
        }

    prompt_path = get_prompt_path(segment)

    if not prompt_path.exists():
        raise FileNotFoundError(
            f"Prompt file not found: {prompt_path}. Please run Day 14 prompt builder first."
        )

    prompt = prompt_path.read_text(encoding="utf-8")

    job.current_stage = "translating"
    job.updated_at = datetime.utcnow()
    segment.status = "translating"
    segment.updated_at = datetime.utcnow()

    add_audit_log(
        db=db,
        job_id=job.id,
        event_type="translation_started",
        stage="translating",
        message=f"Translation started for segment {segment.id}",
    )

    db.commit()

    client = OllamaClient()

    try:
        model_result = client.generate_translation(
            prompt=prompt,
            timeout=timeout_seconds,
        )

        raw_response = model_result.get("response", "")
        cleaned_response = remove_thinking_text(raw_response)
        parsed_json = extract_json_object(raw_response)
        translated_text = extract_translation_text(parsed_json, cleaned_response)

        artifact_paths = save_translation_artifacts(
            job_id=job.id,
            segment_index=segment.segment_index,
            raw_response=raw_response,
            cleaned_response=cleaned_response,
            parsed_json=parsed_json,
        )

        version_no = get_next_version_no(
            db=db,
            job_id=job.id,
            segment_id=segment.id,
        )

        version = TranslationVersion(
            job_id=job.id,
            segment_id=segment.id,
            version_no=version_no,
            model_name=model_result.get("model"),
            prompt_version="day14_translation_prompt_v1",
            source_text=segment.source_text,
            translated_text=translated_text,
            qa_summary=json.dumps(
                {
                    "json_extracted": parsed_json is not None,
                    "glossary_used": parsed_json.get("glossary_used") if parsed_json else None,
                    "notes": parsed_json.get("notes") if parsed_json else None,
                    "artifact_paths": artifact_paths,
                    "metrics": {
                        "total_duration": model_result.get("total_duration"),
                        "load_duration": model_result.get("load_duration"),
                        "prompt_eval_count": model_result.get("prompt_eval_count"),
                        "eval_count": model_result.get("eval_count"),
                    },
                },
                ensure_ascii=False,
            ),
            status="draft",
        )

        db.add(version)

        segment.translated_text = translated_text
        segment.status = "translated"
        segment.updated_at = datetime.utcnow()

        job.current_stage = "translated"
        job.updated_at = datetime.utcnow()

        add_audit_log(
            db=db,
            job_id=job.id,
            event_type="translation_completed",
            stage="translated",
            message=f"Translation completed for segment {segment.id}",
            payload_json=json.dumps(artifact_paths, ensure_ascii=False),
        )

        db.commit()
        db.refresh(version)
        db.refresh(segment)
        db.refresh(job)

        return {
            "status": "ok",
            "skipped": False,
            "job_id": job.id,
            "job_status": job.status,
            "current_stage": job.current_stage,
            "segment": segment_to_dict(segment),
            "translation_version": translation_version_to_dict(version),
            "json_extracted": parsed_json is not None,
            "json": parsed_json,
            "artifact_paths": artifact_paths,
            "model": model_result.get("model"),
            "metrics": {
                "total_duration": model_result.get("total_duration"),
                "load_duration": model_result.get("load_duration"),
                "prompt_eval_count": model_result.get("prompt_eval_count"),
                "eval_count": model_result.get("eval_count"),
            },
        }

    except Exception as exc:
        segment.status = "translation_failed"
        segment.updated_at = datetime.utcnow()
        job.current_stage = "translation_failed"
        job.error_message = str(exc)
        job.updated_at = datetime.utcnow()

        add_error_log(
            db=db,
            job_id=job.id,
            stage="translation",
            error_type=exc.__class__.__name__,
            error_message=str(exc),
        )

        add_audit_log(
            db=db,
            job_id=job.id,
            event_type="translation_failed",
            stage="translation_failed",
            message=str(exc),
        )

        db.commit()

        raise


def translate_job_sync(
    db: Session,
    job_id: str,
    force: bool = False,
    timeout_seconds: int = 900,
) -> dict[str, Any]:
    job = db.get(Job, job_id)

    if not job:
        raise ValueError(f"Job not found: {job_id}")

    segments = db.execute(
        select(Segment)
        .where(Segment.job_id == job_id)
        .order_by(Segment.segment_index.asc())
    ).scalars().all()

    if not segments:
        raise ValueError("No segments found. Please run segmentation first.")

    results = []

    for segment in segments:
        result = translate_segment_sync(
            db=db,
            segment_id=segment.id,
            force=force,
            timeout_seconds=timeout_seconds,
        )
        results.append(result)

    job.current_stage = "job_translated"
    job.updated_at = datetime.utcnow()

    add_audit_log(
        db=db,
        job_id=job.id,
        event_type="job_translation_completed",
        stage="job_translated",
        message=f"Job translated with {len(results)} segment result(s).",
    )

    db.commit()
    db.refresh(job)

    return {
        "status": "ok",
        "job_id": job.id,
        "job_status": job.status,
        "current_stage": job.current_stage,
        "count": len(results),
        "results": results,
    }
