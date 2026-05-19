import json
import urllib.request
from typing import Any

from app.core.settings import get_settings


class OllamaEmbeddingClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.embedding_model = settings.ollama_embedding_model

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def embed_text(self, text: str) -> list[float]:
        text = text.strip()

        if not text:
            raise ValueError("Cannot embed empty text")

        # Newer Ollama API
        try:
            data = self._post_json(
                "/api/embed",
                {
                    "model": self.embedding_model,
                    "input": text,
                },
            )

            embeddings = data.get("embeddings")

            if embeddings and isinstance(embeddings, list):
                first = embeddings[0]

                if isinstance(first, list):
                    return [float(x) for x in first]

                return [float(x) for x in embeddings]

        except Exception:
            pass

        # Older Ollama API fallback
        data = self._post_json(
            "/api/embeddings",
            {
                "model": self.embedding_model,
                "prompt": text,
            },
        )

        embedding = data.get("embedding")

        if not embedding:
            raise RuntimeError(f"Ollama embedding response has no embedding: {data}")

        return [float(x) for x in embedding]
