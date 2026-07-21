"""Stateful transport and freshness checks for observable reading metadata."""

from __future__ import annotations

import time
from collections import deque

from iot_stream.schemas import AnomalyEvent, SensorReading


class TransportQualityDetector:
    """Detect duplicate IDs, sequence anomalies, regressions, and stale data."""

    def __init__(
        self,
        *,
        max_staleness_seconds: float | None = None,
        id_window: int = 1000,
    ):
        self.max_staleness_seconds = max_staleness_seconds
        self._seen_order: deque[str] = deque(maxlen=max(1, id_window))
        self._seen_ids: set[str] = set()
        self._last_sequence: int | None = None
        self._last_timestamp: float | None = None

    def check(
        self, reading: SensorReading, *, received_at: float | None = None
    ) -> list[AnomalyEvent]:
        events: list[AnomalyEvent] = []

        duplicate_event = reading.event_id in self._seen_ids
        if duplicate_event:
            events.append(
                self._event(
                    reading,
                    "duplicate_event",
                    "Event ID was already received; publisher retry or replay detected",
                    "medium",
                    {"event_id": reading.event_id},
                )
            )
        else:
            if len(self._seen_order) == self._seen_order.maxlen:
                self._seen_ids.discard(self._seen_order[0])
            self._seen_order.append(reading.event_id)
            self._seen_ids.add(reading.event_id)

        if self._last_sequence is not None:
            expected = self._last_sequence + 1
            if reading.sequence_number > expected:
                events.append(
                    self._event(
                        reading,
                        "sequence_gap",
                        f"Expected sequence {expected}, received {reading.sequence_number}",
                        "medium",
                        {"expected": expected, "observed": reading.sequence_number},
                    )
                )
            elif reading.sequence_number <= self._last_sequence and not (
                duplicate_event and reading.sequence_number == self._last_sequence
            ):
                events.append(
                    self._event(
                        reading,
                        "sequence_rewind",
                        f"Sequence moved backward or repeated at {reading.sequence_number}",
                        "medium",
                        {
                            "previous": self._last_sequence,
                            "observed": reading.sequence_number,
                        },
                    )
                )

        if self._last_timestamp is not None and reading.timestamp < self._last_timestamp:
            events.append(
                self._event(
                    reading,
                    "timestamp_regression",
                    "Reading timestamp is older than the previous device reading",
                    "medium",
                    {"previous": self._last_timestamp, "observed": reading.timestamp},
                )
            )

        if self.max_staleness_seconds is not None:
            observed_at = time.time() if received_at is None else received_at
            age = observed_at - reading.timestamp
            if age > self.max_staleness_seconds:
                events.append(
                    self._event(
                        reading,
                        "stale_reading",
                        f"Reading arrived {age:.1f}s after its timestamp",
                        "medium",
                        {"age_seconds": round(age, 3)},
                    )
                )

        self._last_sequence = max(
            reading.sequence_number,
            self._last_sequence
            if self._last_sequence is not None
            else reading.sequence_number,
        )
        self._last_timestamp = max(
            reading.timestamp,
            self._last_timestamp
            if self._last_timestamp is not None
            else reading.timestamp,
        )
        return events

    @staticmethod
    def _event(
        reading: SensorReading,
        detector: str,
        description: str,
        severity: str,
        context: dict,
    ) -> AnomalyEvent:
        return AnomalyEvent(
            device_id=reading.device_id,
            timestamp=reading.timestamp,
            detector=detector,
            description=description,
            severity=severity,
            reading=reading,
            context=context,
        )
