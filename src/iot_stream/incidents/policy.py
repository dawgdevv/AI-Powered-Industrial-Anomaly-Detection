"""Deterministic confidence and abstention policy."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite
from typing import Mapping

from iot_stream.incidents.models import Incident, IncidentCategory


class Decision(StrEnum):
    RECOMMEND = "RECOMMEND"
    ESCALATE = "ESCALATE"
    MONITOR = "MONITOR"
    DATA_QUALITY_ALERT = "DATA_QUALITY_ALERT"


@dataclass(frozen=True)
class DecisionResult:
    decision: Decision
    confidence: float
    reason_codes: tuple[str, ...]
    recommendation_threshold: float = field(default=0.75, repr=False)

    def __post_init__(self) -> None:
        if not isfinite(self.confidence) or not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be finite and between 0 and 1")
        if (
            self.decision is Decision.RECOMMEND
            and self.confidence < self.recommendation_threshold
        ):
            raise ValueError("recommendation threshold invariant violated")


class DecisionPolicy:
    def __init__(
        self,
        *,
        detector_weights: Mapping[str, float] | None = None,
        recommend_threshold: float = 0.75,
        monitor_threshold: float = 0.40,
        persistence_step: float = 0.05,
        max_persistence_bonus: float = 0.15,
        data_quality_min_readings: int = 2,
    ):
        self.detector_weights = dict(detector_weights or {"spike": 0.45, "drift": 0.55})
        self.recommend_threshold = recommend_threshold
        self.monitor_threshold = monitor_threshold
        self.persistence_step = max(0.0, persistence_step)
        self.max_persistence_bonus = max(0.0, max_persistence_bonus)
        self.data_quality_min_readings = max(1, data_quality_min_readings)
        self._validate_configuration()

    def evaluate(self, incident: Incident) -> DecisionResult:
        try:
            if incident.category is IncidentCategory.DATA_QUALITY:
                return self._evaluate_data_quality(incident)
            return self._evaluate_equipment(incident)
        except Exception:
            return DecisionResult(
                decision=Decision.ESCALATE,
                confidence=0.0,
                reason_codes=("policy_failure_safe_escalation",),
            )

    def _evaluate_equipment(self, incident: Incident) -> DecisionResult:
        total_weight = sum(self.detector_weights.values())
        evidence_weight = sum(
            self.detector_weights.get(detector, 0.0)
            for detector in set(incident.detectors)
        )
        base = evidence_weight / total_weight if total_weight else 0.0
        persistence = min(
            max(incident.affected_reading_count - 1, 0) * self.persistence_step,
            self.max_persistence_bonus,
        )
        confidence = min(1.0, max(0.0, base + persistence))
        known = set(incident.detectors) & self.detector_weights.keys()

        if not known or confidence < self.monitor_threshold:
            return DecisionResult(
                Decision.ESCALATE,
                confidence,
                ("insufficient_detector_agreement", "human_review_required"),
            )
        if confidence < self.recommend_threshold:
            return DecisionResult(
                Decision.MONITOR,
                confidence,
                ("partial_detector_agreement",),
            )
        return self._recommend(confidence)

    def _evaluate_data_quality(self, incident: Incident) -> DecisionResult:
        confidence = min(
            1.0,
            incident.affected_reading_count / self.data_quality_min_readings,
        )
        if incident.affected_reading_count < self.data_quality_min_readings:
            return DecisionResult(
                Decision.MONITOR,
                confidence,
                ("data_quality_not_yet_sustained",),
            )
        return DecisionResult(
            Decision.DATA_QUALITY_ALERT,
            confidence,
            ("sustained_data_quality_failure", "inspect_sensor_gateway_or_network"),
        )

    def _recommend(self, confidence: float) -> DecisionResult:
        if confidence < self.recommend_threshold:
            raise ValueError("recommendation threshold invariant violated")
        return DecisionResult(
            Decision.RECOMMEND,
            confidence,
            ("strong_detector_agreement",),
            self.recommend_threshold,
        )

    def _validate_configuration(self) -> None:
        if not 0.0 <= self.monitor_threshold <= self.recommend_threshold <= 1.0:
            raise ValueError("decision thresholds must be ordered within [0, 1]")
        if not self.detector_weights or any(
            not isfinite(weight) or weight < 0.0
            for weight in self.detector_weights.values()
        ):
            raise ValueError("detector weights must be finite and non-negative")
        if sum(self.detector_weights.values()) <= 0.0:
            raise ValueError("at least one detector weight must be positive")
