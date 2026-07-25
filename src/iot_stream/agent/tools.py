"""Small read-only tools exposed to the bounded incident explanation agent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from iot_stream.incidents.models import Incident
from iot_stream.schemas import SensorReading


@dataclass(frozen=True)
class AgentTool:
    name: str
    description: str
    handler: Callable[["ToolContext"], dict[str, Any]]


@dataclass(frozen=True)
class ToolContext:
    incident: Incident
    reading: SensorReading
    evidence: list[dict[str, object]]
    healthy_reading_count: int
    healthy_readings_required: int


def incident_context(context: ToolContext) -> dict[str, Any]:
    """Return only detector evidence that the model may describe."""
    incident = context.incident
    return {
        "incident_id": incident.incident_id,
        "equipment_type": context.reading.equipment_type,
        "equipment_name": context.reading.equipment_name,
        "detectors": sorted(incident.detectors),
        "affected_reading_count": incident.affected_reading_count,
        "peak_observed_value": incident.peak_observed_value,
        "decision": incident.decision,
        "reason_codes": incident.reason_codes,
    }


def retrieved_precedents(context: ToolContext) -> dict[str, Any]:
    """Return cited precedent summaries, never arbitrary database content."""
    return {
        "precedents": [
            {
                "incident_id": item.get("incident_id"),
                "fault_family": item.get("fault_family"),
                "verified": item.get("verified"),
                "summary": item.get("summary"),
            }
            for item in context.evidence[:3]
        ]
    }


def recovery_status(context: ToolContext) -> dict[str, Any]:
    return {
        "healthy_reading_count": context.healthy_reading_count,
        "healthy_readings_required": context.healthy_readings_required,
    }


EXPORTED_TOOLS = (
    AgentTool("get_incident_context", "Read current detector and policy evidence.", incident_context),
    AgentTool("get_retrieved_precedents", "Read the retrieved historical cases already selected by retrieval.", retrieved_precedents),
    AgentTool("get_recovery_status", "Read agent recovery progress.", recovery_status),
)


def run_tools(context: ToolContext) -> dict[str, dict[str, Any]]:
    return {tool.name: tool.handler(context) for tool in EXPORTED_TOOLS}
