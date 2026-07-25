"""Typed contracts for local incident retrieval.

These types intentionally do not depend on Chroma or LiteLLM. They form the
boundary between the application and whichever embedding/vector client is
configured by the deployment.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class RetrievalQuery:
    """A semantically searchable incident description plus required filters."""

    text: str
    equipment_type: str
    sensor_type: str
    incident_category: str
    limit: int = 3

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("retrieval text cannot be empty")
        if not all(
            value.strip()
            for value in (self.equipment_type, self.sensor_type, self.incident_category)
        ):
            raise ValueError("equipment_type, sensor_type, and incident_category are required")
        if not 1 <= self.limit <= 10:
            raise ValueError("limit must be between 1 and 10")


@dataclass(frozen=True)
class RetrievalMatch:
    """One source-backed incident returned by the vector database.

    ``distance`` is the raw value returned by the configured Chroma collection.
    It is deliberately not converted into a confidence score because distance
    scales depend on the embedding model and collection configuration.
    """

    incident_id: str
    retrieval_text: str
    metadata: Mapping[str, str | bool]
    distance: float | None

    @property
    def verified(self) -> bool:
        return self.metadata.get("verified") is True

    @property
    def source_url(self) -> str | None:
        value = self.metadata.get("source_url")
        return value if isinstance(value, str) else None

