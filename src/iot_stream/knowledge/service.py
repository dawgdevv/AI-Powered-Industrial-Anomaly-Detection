"""Application factory for the local Chroma incident-retrieval service."""

from __future__ import annotations

import os
from pathlib import Path

from iot_stream.knowledge.chroma_store import ChromaIncidentStore
from iot_stream.knowledge.litellm_embeddings import (
    LiteLLMEmbeddingClient,
    LiteLLMEmbeddingSettings,
)
from iot_stream.knowledge.retriever import IncidentRetriever


def build_knowledge_store() -> ChromaIncidentStore:
    path = Path(os.getenv("CHROMA_PERSIST_PATH", "data/chroma"))
    return ChromaIncidentStore(path)


def build_incident_retriever() -> IncidentRetriever:
    store = build_knowledge_store()
    embeddings = LiteLLMEmbeddingClient(LiteLLMEmbeddingSettings.from_env())
    return IncidentRetriever(store.collection, embeddings)
