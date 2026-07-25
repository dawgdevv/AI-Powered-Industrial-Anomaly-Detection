"""Persistent local Chroma store for source-backed incident records."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import chromadb

from iot_stream.knowledge.models import RetrievalMatch
from iot_stream.telemetry import span

COLLECTION_NAME = "industrial_incidents"
CORPUS_PATH = Path(__file__).with_name("incidents.json")


class ChromaIncidentStore:
    """Owns collection creation and deterministic indexing of the local corpus."""

    def __init__(self, persist_path: Path, collection_name: str = COLLECTION_NAME):
        self.persist_path = persist_path
        self._client = chromadb.PersistentClient(path=str(persist_path))
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
            embedding_function=None,
        )

    @property
    def collection(self) -> Any:
        return self._collection

    def count(self) -> int:
        return self._collection.count()

    def reset(self) -> None:
        self._client.delete_collection(self._collection.name)
        self._collection = self._client.get_or_create_collection(
            name=self._collection.name,
            metadata={"hnsw:space": "cosine"},
            embedding_function=None,
        )

    def index_corpus(
        self,
        embeddings: "EmbeddingBatchClient",
        *,
        corpus_path: Path = CORPUS_PATH,
        batch_size: int = 32,
    ) -> int:
        records = _load_records(corpus_path)
        documents = list(_documents(records))
        if not documents:
            return 0

        with span("knowledge.index", document_count=len(documents)):
            for batch in _batches(documents, batch_size):
                texts = [item["document"] for item in batch]
                vectors = embeddings.embed_documents(texts)
                if len(vectors) != len(batch):
                    raise ValueError("embedding client returned the wrong number of vectors")
                self._collection.upsert(
                    ids=[item["id"] for item in batch],
                    documents=texts,
                    metadatas=[item["metadata"] for item in batch],
                    embeddings=vectors,
                )
        return len(documents)


class EmbeddingBatchClient:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


def _load_records(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, list):
        raise ValueError("incident corpus must contain a JSON array")
    return value


def _documents(records: Iterable[dict[str, Any]]) -> Iterable[dict[str, Any]]:
    for record in records:
        source = record["source"]
        document = "\n".join(
            (
                f"Title: {record['title']}",
                f"Equipment: {record['equipment_type']}",
                f"Pattern: {record['pattern_type']}",
                f"Fault family: {record['fault_family']}",
                f"Summary: {record['retrieval_text']}",
                f"Reported cause: {record['confirmed_or_reported_cause']}",
                f"Outcome: {record['outcome_or_resolution']}",
                f"Operational next step: {record['derived_operational_next_step']}",
            )
        )
        for sensor_type in record["sensor_types"]:
            yield {
                "id": f"{record['incident_id']}:{sensor_type}",
                "document": document,
                "metadata": {
                    "incident_id": record["incident_id"],
                    "equipment_type": record["equipment_type"],
                    "sensor_type": sensor_type,
                    "incident_category": record["incident_category"],
                    "pattern_type": record["pattern_type"],
                    "fault_family": record["fault_family"],
                    "source_kind": record["source_kind"],
                    "verified": record["verified"],
                    "source_url": source["url"],
                },
            }


def _batches(items: list[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]
