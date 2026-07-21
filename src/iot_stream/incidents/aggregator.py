"""Group anomaly events into category-safe, lifecycle-aware incidents."""

from __future__ import annotations

from iot_stream.incidents.models import Incident, IncidentCategory, IncidentState
from iot_stream.incidents.policy import Decision, DecisionResult
from iot_stream.schemas import AnomalyEvent


EQUIPMENT_DETECTORS = frozenset({"spike", "drift"})
DATA_QUALITY_DETECTORS = frozenset(
    {
        "dropout",
        "duplicate_event",
        "sequence_gap",
        "sequence_rewind",
        "timestamp_regression",
        "stale_reading",
    }
)
SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}


def category_for_detector(detector: str) -> IncidentCategory:
    if detector in DATA_QUALITY_DETECTORS:
        return IncidentCategory.DATA_QUALITY
    return IncidentCategory.EQUIPMENT_CONDITION


class IncidentAggregator:
    def __init__(
        self,
        *,
        aggregation_window_seconds: float = 300.0,
        quiet_period_seconds: float = 60.0,
        notification_cooldown_seconds: float = 120.0,
    ):
        self.aggregation_window_seconds = aggregation_window_seconds
        self.quiet_period_seconds = quiet_period_seconds
        self.notification_cooldown_seconds = notification_cooldown_seconds
        self._active: dict[tuple[str, IncidentCategory], Incident] = {}
        self._counter = 0

    def aggregate(self, event: AnomalyEvent) -> Incident:
        category = category_for_detector(event.detector)
        key = (event.device_id, category)
        incident = self._active.get(key)
        if (
            incident is None
            or incident.state is IncidentState.RESOLVED
            or event.timestamp - incident.last_seen > self.aggregation_window_seconds
        ):
            incident = self._new_incident(event, category)
            self._active[key] = incident
        else:
            self._update_incident(incident, event)
        return incident

    def resolve_quiet(self, device_id: str, timestamp: float) -> list[Incident]:
        resolved: list[Incident] = []
        for (active_device, _category), incident in self._active.items():
            if (
                active_device == device_id
                and incident.state is not IncidentState.RESOLVED
                and timestamp - incident.last_seen >= self.quiet_period_seconds
            ):
                incident.state = IncidentState.RESOLVED
                incident.reason_codes.append("quiet_period_elapsed")
                resolved.append(incident)
        return resolved

    def notification_due(self, incident: Incident, timestamp: float) -> bool:
        if (
            incident.last_notified_at is not None
            and timestamp - incident.last_notified_at < self.notification_cooldown_seconds
        ):
            return False
        incident.last_notified_at = timestamp
        return True

    def apply_decision(self, incident: Incident, result: DecisionResult) -> Incident:
        incident.confidence = result.confidence
        incident.decision = result.decision.value
        incident.reason_codes = list(
            dict.fromkeys([*incident.reason_codes, *result.reason_codes])
        )
        if result.decision is Decision.RECOMMEND:
            incident.state = IncidentState.RECOMMENDED
        elif result.decision in {Decision.ESCALATE, Decision.DATA_QUALITY_ALERT}:
            incident.state = IncidentState.ESCALATED
        else:
            incident.state = IncidentState.INVESTIGATING
        return incident

    def _new_incident(
        self, event: AnomalyEvent, category: IncidentCategory
    ) -> Incident:
        self._counter += 1
        incident = Incident(
            incident_id=f"INC-{self._counter:06d}",
            device_id=event.device_id,
            category=category,
            state=IncidentState.OPEN,
            first_seen=event.timestamp,
            last_seen=event.timestamp,
        )
        self._update_incident(incident, event)
        return incident

    @staticmethod
    def _update_incident(incident: Incident, event: AnomalyEvent) -> None:
        incident.first_seen = min(incident.first_seen, event.timestamp)
        incident.last_seen = max(incident.last_seen, event.timestamp)
        incident.detectors.add(event.detector)
        if event.reading.event_id not in incident._reading_ids:
            incident._reading_ids.add(event.reading.event_id)
            incident.affected_reading_count += 1

        if SEVERITY_RANK.get(event.severity, 0) > SEVERITY_RANK.get(
            incident.peak_severity, 0
        ):
            incident.peak_severity = event.severity

        observed = event.reading.vibration
        if observed is not None and (
            incident.peak_observed_value is None
            or abs(observed) > abs(incident.peak_observed_value)
        ):
            incident.peak_observed_value = observed

        reason = f"detector_{event.detector}"
        if reason not in incident.reason_codes:
            incident.reason_codes.append(reason)
        if incident.affected_reading_count > 1 or len(incident.detectors) > 1:
            incident.state = IncidentState.INVESTIGATING
