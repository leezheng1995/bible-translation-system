from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.ollama_client import OllamaClient


router = APIRouter(
    prefix="/ollama",
    tags=["ollama"],
)


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    model: Optional[str] = None
    model_type: str = "default"


class GenerateResponse(BaseModel):
    model: str
    response: str
    done: bool


@router.get("/health")
def ollama_health():
    client = OllamaClient()
    models = client.list_models()

    return {
        "status": "ok",
        "base_url": client.base_url,
        "models": models,
    }


@router.get("/models")
def list_models():
    client = OllamaClient()

    return {
        "models": client.list_models(),
        "translation_model": client.translation_model,
        "review_model": client.review_model,
        "default_model": client.default_model,
    }


@router.post("/generate", response_model=GenerateResponse)
def generate_text(request: GenerateRequest):
    client = OllamaClient()

    return client.generate(
        prompt=request.prompt,
        model=request.model,
        model_type=request.model_type,
    )
