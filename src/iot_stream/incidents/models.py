"""Incident domain models shared by aggregation and decision policy."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class IncidentCategory(StrEnum):
    EQUIPMENT_CONDITION = "EQUIPMENT_CONDITION"
    DATA_QUALITY = "DATA_QUALITY"


class IncidentState(StrEnum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    RECOMMENDED = "RECOMMENDED"
    ESCALATED = "ESCALATED"
    INSPECTION = "INSPECTION"
    READY_TO_RESOLVE = "READY_TO_RESOLVE"
    RESOLVED = "RESOLVED"


@dataclass
class Incident:
    incident_id: str
    device_id: str
    category: IncidentCategory
    state: IncidentState
    first_seen: float
    last_seen: float
    affected_reading_count: int = 0
    detectors: set[str] = field(default_factory=set)
    peak_severity: str = "low"
    peak_observed_value: float | None = None
    confidence: float = 0.0
    decision: str | None = None
    reason_codes: list[str] = field(default_factory=list)
    retrieved_incident_ids: list[str] = field(default_factory=list)
    retrieval_top_distance: float | None = None
    retrieval_second_distance: float | None = None
    last_notified_at: float | None = None
    trace_id: str | None = None
    _reading_ids: set[str] = field(default_factory=set, repr=False)
