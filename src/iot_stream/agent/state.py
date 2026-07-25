"""Structured data passed between the agent, tools, model, and API."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class AgentAssessment:
    incident_id: str
    title: str
    explanation: str
    operator_action: str
    likely_fault: str | None
    cited_incident_ids: list[str]
    abstained: bool
    abstention_reason: str | None
    model: str | None
    model_fallback: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
