from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Job, Segment
from app.services.ollama_client import OllamaClient, extract_json_object, remove_thinking_text


router = APIRouter(
    prefix="/model-router",
    tags=["model-router"],
)


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    model: Optional[str] = None
    model_type: str = "default"
    temperature: float = 0.2
    num_ctx: int = 4096
    num_predict: int = 1024
    timeout_seconds: int = 600
    extract_json: bool = False


class PromptFileGenerateRequest(BaseModel):
    path: str = Field(..., min_length=1)
    model_type: str = "translation"
    timeout_seconds: int = 600
    extract_json: bool = True


class SegmentDryRunRequest(BaseModel):
    timeout_seconds: int = 600
    extract_json: bool = True


def safe_read_storage_file(path: str) -> str:
    target = Path(path)

    if not target.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    resolved = target.resolve()
    storage_root = Path("/app/storage").resolve()

    if storage_root not in resolved.parents and resolved != storage_root:
        raise HTTPException(status_code=400, detail="Only files under /app/storage are allowed")

    return target.read_text(encoding="utf-8")


def model_result_to_response(result: dict[str, Any], extract_json: bool = False) -> dict[str, Any]:
    raw_response = result.get("response", "")
    cleaned_response = remove_thinking_text(raw_response)
    parsed_json = extract_json_object(raw_response) if extract_json else None

    return {
        "status": "ok",
        "model": result.get("model"),
        "done": result.get("done"),
        "response_length": len(raw_response),
        "cleaned_response_length": len(cleaned_response),
        "response": raw_response,
        "cleaned_response": cleaned_response,
        "json_extracted": parsed_json is not None,
        "json": parsed_json,
        "metrics": {
            "total_duration": result.get("total_duration"),
            "load_duration": result.get("load_duration"),
            "prompt_eval_count": result.get("prompt_eval_count"),
            "eval_count": result.get("eval_count"),
        },
    }


@router.get("/health")
def model_router_health():
    client = OllamaClient()

    return {
        "status": "ok",
        "base_url": client.base_url,
        "models": client.list_models(),
        "translation_model": client.translation_model,
        "review_model": client.review_model,
        "embedding_model": client.embedding_model,
        "default_model": client.default_model,
    }


@router.post("/generate")
def generate_text(request: GenerateRequest):
    client = OllamaClient()

    result = client.generate(
        prompt=request.prompt,
        model=request.model,
        model_type=request.model_type,
        temperature=request.temperature,
        num_ctx=request.num_ctx,
        num_predict=request.num_predict,
        timeout=request.timeout_seconds,
    )

    return model_result_to_response(
        result=result,
        extract_json=request.extract_json,
    )


@router.post("/prompt-file/generate")
def generate_from_prompt_file(request: PromptFileGenerateRequest):
    prompt = safe_read_storage_file(request.path)

    client = OllamaClient()

    result = client.generate(
        prompt=prompt,
        model_type=request.model_type,
        temperature=0.1,
        num_ctx=4096,
        num_predict=1024,
        timeout=request.timeout_seconds,
    )

    response = model_result_to_response(
        result=result,
        extract_json=request.extract_json,
    )

    response["prompt_path"] = request.path
    response["prompt_length"] = len(prompt)

    return response


@router.post("/segment/{segment_id}/translation-dry-run")
def translation_dry_run_for_segment(
    segment_id: str,
    request: SegmentDryRunRequest | None = None,
    db: Session = Depends(get_db),
):
    segment = db.get(Segment, segment_id)

    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")

    job = db.get(Job, segment.job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    prompt_path = (
        Path("/app/storage")
        / "jobs"
        / segment.job_id
        / "prompts"
        / f"segment_{segment.segment_index:04d}_translation_prompt.txt"
    )

    if not prompt_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Prompt file not found: {prompt_path}. Please run Day 14 prompt builder first.",
        )

    prompt = prompt_path.read_text(encoding="utf-8")

    timeout_seconds = request.timeout_seconds if request else 600
    extract_json = request.extract_json if request else True

    client = OllamaClient()

    result = client.generate_translation(
        prompt=prompt,
        timeout=timeout_seconds,
    )

    response = model_result_to_response(
        result=result,
        extract_json=extract_json,
    )

    response["job_id"] = job.id
    response["segment_id"] = segment.id
    response["segment_index"] = segment.segment_index
    response["prompt_path"] = str(prompt_path)
    response["prompt_length"] = len(prompt)

    return response


@router.post("/test/translation")
def test_translation():
    client = OllamaClient()

    prompt = """You are a Bible translation assistant.
Translate the following English sentence into formal Traditional Chinese.
Return only valid JSON. Do not include markdown.

Source:
In the beginning God created the heavens and the earth.

JSON format:
{
  "translation": "<Traditional Chinese translation>",
  "notes": "<brief note in Traditional Chinese>"
}
"""

    result = client.generate_translation(
        prompt=prompt,
        timeout=600,
    )

    response = model_result_to_response(
        result=result,
        extract_json=True,
    )

    response["prompt"] = prompt

    return response
