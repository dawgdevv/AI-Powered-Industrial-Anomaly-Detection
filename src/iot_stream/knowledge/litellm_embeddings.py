"""LiteLLM gateway adapter for Mistral-compatible embeddings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class LiteLLMEmbeddingSettings:
    api_base: str
    api_key: str
    model: str
    timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls) -> "LiteLLMEmbeddingSettings":
        api_key = os.getenv("LITELLM_API_KEY")
        if not api_key:
            raise RuntimeError("LITELLM_API_KEY is required for knowledge-base embeddings")
        return cls(
            api_base=os.getenv("LITELLM_API_BASE", "http://127.0.0.1:4000/v1").rstrip("/"),
            api_key=api_key,
            model=os.getenv("LITELLM_EMBEDDING_MODEL", "mistral-embed"),
            timeout_seconds=float(os.getenv("LITELLM_TIMEOUT_SECONDS", "30")),
        )


class LiteLLMEmbeddingClient:
    """Calls LiteLLM's OpenAI-compatible embeddings endpoint."""

    def __init__(self, settings: LiteLLMEmbeddingSettings):
        self._settings = settings

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = httpx.post(
            f"{self._settings.api_base}/embeddings",
            headers={"Authorization": f"Bearer {self._settings.api_key}"},
            json={"model": self._settings.model, "input": texts},
            timeout=self._settings.timeout_seconds,
        )
        if response.is_error:
            raise RuntimeError(
                f"LiteLLM embeddings request failed ({response.status_code}): {response.text}"
            )
        payload: dict[str, Any] = response.json()
        rows = payload.get("data")
        if not isinstance(rows, list) or len(rows) != len(texts):
            raise RuntimeError("LiteLLM returned an invalid embeddings response")
        try:
            return [list(row["embedding"]) for row in rows]
        except (KeyError, TypeError) as error:
            raise RuntimeError("LiteLLM response did not contain embeddings") from error
