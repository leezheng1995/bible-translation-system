import json
import os
import urllib.request
from typing import Any, Dict, List, Optional


class OllamaClient:
    def __init__(self) -> None:
        self.base_url = os.getenv(
            "OLLAMA_BASE_URL",
            "http://host.docker.internal:11434"
        ).rstrip("/")

        self.translation_model = os.getenv(
            "OLLAMA_TRANSLATION_MODEL",
            "qwen3:14b"
        )

        self.review_model = os.getenv(
            "OLLAMA_REVIEW_MODEL",
            "gemma4:26b"
        )

        self.default_model = os.getenv(
            "OLLAMA_DEFAULT_MODEL",
            self.translation_model
        )

    def get_model_by_type(self, model_type: str) -> str:
        if model_type == "translation":
            return self.translation_model

        if model_type == "review":
            return self.review_model

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
