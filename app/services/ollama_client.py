import json
import urllib.request
from typing import Any, Dict, List, Optional

from app.core.settings import get_settings


class OllamaClient:
    def __init__(self) -> None:
        settings = get_settings()

        self.base_url = settings.ollama_base_url.rstrip("/")
        self.translation_model = settings.ollama_translation_model
        self.review_model = settings.ollama_review_model
        self.default_model = settings.ollama_default_model
        self.embedding_model = settings.ollama_embedding_model

    def get_model_by_type(self, model_type: str) -> str:
        if model_type == "translation":
            return self.translation_model

        if model_type == "review":
            return self.review_model

        if model_type == "embedding":
            return self.embedding_model

        return self.default_model

    def list_models(self) -> List[str]:
        url = f"{self.base_url}/api/tags"

        response = urllib.request.urlopen(url, timeout=10).read().decode()
        data = json.loads(response)

        return [
            model.get("name")
            for model in data.get("models", [])
            if model.get("name")
        ]

    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        model_type: str = "default",
        stream: bool = False,
    ) -> Dict[str, Any]:
        selected_model = model or self.get_model_by_type(model_type)

        payload = {
            "model": selected_model,
            "prompt": prompt,
            "stream": stream,
        }

        request = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        response = urllib.request.urlopen(request, timeout=180).read().decode()
        data = json.loads(response)

        return {
            "model": selected_model,
            "response": data.get("response", ""),
            "done": data.get("done", False),
        }

    def embed(
        self,
        text: str,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        selected_model = model or self.embedding_model

        payload = {
            "model": selected_model,
            "input": text,
        }

        request = urllib.request.Request(
            f"{self.base_url}/api/embed",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        response = urllib.request.urlopen(request, timeout=60).read().decode()
        data = json.loads(response)

        return {
            "model": selected_model,
            "embeddings": data.get("embeddings", []),
        }
