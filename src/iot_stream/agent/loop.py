"""Small deterministic agent loop for anomaly follow-up and recovery."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from iot_stream.agent.planner import MistralExplanationClient, deterministic_assessment
from iot_stream.agent.state import AgentAssessment
from iot_stream.agent.tools import ToolContext, run_tools
from iot_stream.incidents.models import Incident
from iot_stream.schemas import AnomalyEvent, SensorReading
from iot_stream.telemetry import event, record_assessment, span


@dataclass(frozen=True)
class RecoveryUpdate:
    incident_id: str
    healthy_reading_count: int
    resolved: bool = False


class IncidentMonitoringAgent:
    """Track recovery after a detected equipment anomaly.

    A reading is healthy only when it has vibration data and neither equipment
    detector fired for that reading.  The required consecutive count is an
    application safety rule, not a model decision.
    """

    def __init__(self, healthy_readings_to_resolve: int = 5, recovery_stability_seconds: float = 8.0):
        self.healthy_readings_to_resolve = healthy_readings_to_resolve
        self.recovery_stability_seconds = max(0.0, recovery_stability_seconds)
        self._model = MistralExplanationClient.from_env()

    @property
    def model_available(self) -> bool:
        return self._model is not None

    def assess(self, incident: Incident, reading: SensorReading, evidence: list[dict[str, object]], healthy_reading_count: int = 0, *, use_model: bool = True) -> AgentAssessment:
        started_at = perf_counter()
        context = ToolContext(incident, reading, evidence, healthy_reading_count, self.healthy_readings_to_resolve)
        tool_results = run_tools(context)
        has_verified_precedent = any(item.get("verified") is True for item in evidence)
        use_model = use_model and self._model is not None and has_verified_precedent
        attempted_mode = "mistral" if use_model else "deterministic"
        with span(
            "agent.explain",
            incident_id=incident.incident_id,
            agent_attempted_mode=attempted_mode,
            agent_has_verified_precedent=has_verified_precedent,
            model=self._model.model if use_model and self._model else "deterministic",
        ) as active_span:
            try:
                assessment = self._model.explain(incident.incident_id, tool_results) if use_model and self._model else deterministic_assessment(incident.incident_id, tool_results)
            except Exception:
                assessment = deterministic_assessment(incident.incident_id, tool_results)
            active_span.set_attribute("agent.abstained", assessment.abstained)
            active_span.set_attribute("agent.model_fallback", assessment.model_fallback)
            active_span.set_attribute("agent.cited_count", len(assessment.cited_incident_ids))
            active_span.set_attribute("agent.outcome", "abstained" if assessment.abstained else "assessment_created")
            mode = "mistral" if assessment.model and not assessment.model_fallback else "deterministic"
            record_assessment(
                attempted_mode=attempted_mode,
                final_mode=mode,
                fallback=assessment.model_fallback,
                abstained=assessment.abstained,
                duration_seconds=perf_counter() - started_at,
            )
            event(
                "agent.assessment_created",
                incident_id=incident.incident_id,
                agent_attempted_mode=attempted_mode,
                agent_final_mode=mode,
                agent_fallback=assessment.model_fallback,
                agent_abstained=assessment.abstained,
            )
            return assessment

    def activate(self, incident: Incident, workflow: dict[str, float | int]) -> None:
        workflow.setdefault("started_at", incident.first_seen)
        workflow.setdefault("healthy_reading_count", 0)
        workflow.setdefault("healthy_since", None)
        workflow.setdefault("recovery_state", "watching")

    def observe(
        self,
        incident: Incident,
        workflow: dict[str, float | int],
        reading: SensorReading,
        events: list[AnomalyEvent],
        equipment_healthy: bool | None = None,
        knowledge_ready: bool = True,
    ) -> RecoveryUpdate:
        with span(
            "agent.monitor_recovery",
            incident_id=incident.incident_id,
            device_id=reading.device_id,
            reading_sequence=reading.sequence_number,
        ) as active_span:
            has_equipment_event = any(event.detector in {"spike", "drift"} for event in events)
            if has_equipment_event or equipment_healthy is False or reading.vibration is None:
                workflow["healthy_reading_count"] = 0
                workflow["healthy_since"] = None
                workflow["recovery_state"] = "watching"
                active_span.set_attribute("agent.recovery_reset", True)
                active_span.set_attribute("agent.recovery_state", "watching")
                return RecoveryUpdate(incident.incident_id, 0)

            count = min(
                self.healthy_readings_to_resolve,
                int(workflow.get("healthy_reading_count", 0)) + 1,
            )
            workflow["healthy_reading_count"] = count
            healthy_since = workflow.get("healthy_since")
            if not isinstance(healthy_since, (int, float)):
                healthy_since = reading.timestamp
                workflow["healthy_since"] = healthy_since
            stable_seconds = max(0.0, reading.timestamp - healthy_since)
            enough_readings = count >= self.healthy_readings_to_resolve
            enough_time = stable_seconds >= self.recovery_stability_seconds
            resolved = enough_readings and enough_time and knowledge_ready
            recovery_state = (
                "awaiting_knowledge" if enough_readings and not knowledge_ready
                else "observing_normal" if enough_readings and not enough_time
                else "resolved" if resolved
                else "stabilizing"
            )
            workflow["recovery_state"] = recovery_state
            active_span.set_attribute("agent.healthy_reading_count", count)
            active_span.set_attribute("agent.healthy_stable_seconds", stable_seconds)
            active_span.set_attribute("agent.knowledge_ready", knowledge_ready)
            active_span.set_attribute("agent.auto_resolved", resolved)
            active_span.set_attribute("agent.recovery_state", recovery_state)
            return RecoveryUpdate(incident.incident_id, count, resolved)
