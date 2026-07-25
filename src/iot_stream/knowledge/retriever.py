"""Custom inference layer for a locally configured Chroma incident store.

The application owns Chroma construction, persistence, document indexing, and
embedding configuration. This module only performs filtered retrieval and
normalizes Chroma's response for the policy and agent layers.
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol, Sequence

from iot_stream.knowledge.models import RetrievalMatch, RetrievalQuery
from iot_stream.telemetry import span


class EmbeddingClient(Protocol):
    """Minimal interface supplied by the LiteLLM/Mistral integration."""

    def embed_query(self, text: str) -> Sequence[float]: ...


class ChromaCollection(Protocol):
    """The small part of Chroma's collection API used at inference time."""

    def query(self, **kwargs: Any) -> Mapping[str, Any]: ...

    def get(self, **kwargs: Any) -> Mapping[str, Any]: ...


class IncidentRetriever:
    """Retrieve only incidents that fit the current equipment and sensor scope."""

    def __init__(self, collection: ChromaCollection, embeddings: EmbeddingClient):
        self._collection = collection
        self._embeddings = embeddings

    def search(self, query: RetrievalQuery) -> list[RetrievalMatch]:
        vector = list(self._embeddings.embed_query(query.text))
        if not vector:
            raise ValueError("embedding client returned an empty vector")

        with span(
            "knowledge.retrieve",
            knowledge_collection="water_treatment_incidents",
            equipment_type=query.equipment_type,
            sensor_type=query.sensor_type,
            incident_category=query.incident_category,
        ) as active_span:
            result = self._collection.query(
                query_embeddings=[vector],
                n_results=query.limit,
                where={
                    "$and": [
                        {"equipment_type": query.equipment_type},
                        {"sensor_type": query.sensor_type},
                        {"incident_category": query.incident_category},
                    ]
                },
                include=["documents", "metadatas", "distances"],
            )
            matches = self._matches_from_result(result)
            active_span.set_attribute("retrieval.result_count", len(matches))
            if matches:
                active_span.set_attribute("retrieval.top_incident_id", matches[0].incident_id)
                active_span.set_attribute("retrieval.top_distance", matches[0].distance if matches[0].distance is not None else -1.0)
                active_span.set_attribute("retrieval.top_source_kind", str(matches[0].metadata.get("source_kind", "unknown")))
            return matches

    def get_incidents(self, incident_ids: Sequence[str]) -> list[RetrievalMatch]:
        """Load cited incident records without running another semantic search."""
        if not incident_ids:
            return []
        result = self._collection.get(
            ids=list(incident_ids),
            include=["documents", "metadatas"],
        )
        return self._matches_from_result(result)

    @staticmethod
    def _matches_from_result(result: Mapping[str, Any]) -> list[RetrievalMatch]:
        ids = IncidentRetriever._first_row(result.get("ids", []))
        documents = IncidentRetriever._first_row(result.get("documents", []))
        metadatas = IncidentRetriever._first_row(result.get("metadatas", []))
        distances = IncidentRetriever._first_row(result.get("distances", []))

        matches: list[RetrievalMatch] = []
        for index, incident_id in enumerate(ids):
            metadata = metadatas[index] if index < len(metadatas) else {}
            distance = distances[index] if index < len(distances) else None
            normalized_metadata = (
                dict(metadata) if isinstance(metadata, Mapping) else {}
            )
            matches.append(
                RetrievalMatch(
                    incident_id=str(normalized_metadata.get("incident_id", incident_id)),
                    retrieval_text=str(documents[index]) if index < len(documents) else "",
                    metadata=normalized_metadata,
                    distance=float(distance) if isinstance(distance, (float, int)) else None,
                )
            )
        return matches

    @staticmethod
    def _first_row(value: Any) -> list[Any]:
        """Normalize Chroma query (nested) and get (flat) response fields."""
        if not isinstance(value, list) or not value:
            return []
        return value[0] if isinstance(value[0], list) else value
