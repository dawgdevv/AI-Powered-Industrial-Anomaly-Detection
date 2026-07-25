"""In-memory live processing runtime shared by all API clients."""

from __future__ import annotations

import asyncio
import time
import os
from pathlib import Path
from collections import deque
from contextlib import suppress
from typing import Any

from iot_stream.api.models import PolicyConfig, ReviewRequest
from iot_stream.incidents import DecisionPolicy, Incident, IncidentAggregator
from iot_stream.incidents.models import IncidentCategory, IncidentState
from iot_stream.ingestion.tcp_client import stream_readings
from iot_stream.pipeline.detectors import DeviceDetectorSet
from iot_stream.schemas import AnomalyEvent, SensorReading
from iot_stream.knowledge import RetrievalQuery, build_incident_retriever
from iot_stream.persistence import RuntimeDatabase


CONFIGURED_FLEET_SIZE = 6
_DEFAULT_DATABASE = object()


class RuntimeStore:
    def __init__(
        self,
        *,
        trend_size: int = 90,
        activity_size: int = 120,
        client_queue_size: int = 256,
    ):
        self.trend_size = trend_size
        self.activity: deque[dict[str, Any]] = deque(maxlen=activity_size)
        self.client_queue_size = client_queue_size
        self.sensors: dict[str, dict[str, Any]] = {}
        self.trends: dict[str, deque[float | None]] = {}
        self.incidents: dict[str, Incident] = {}
        self.acknowledged: set[str] = set()
        self.manually_resolved: set[str] = set()
        self.retrieval_evidence: dict[str, list[dict[str, object]]] = {}
        self.reviews: dict[str, dict[str, object]] = {}
        self.policy_config = PolicyConfig()
        self.stream_status = "connecting"
        self.stream_error: str | None = None
        self.last_reading_at: float | None = None
        self.started_at = time.time()
        self._event_id = 0
        self._clients: set[asyncio.Queue[dict[str, Any]]] = set()

    def sensor_snapshot(self, device_id: str) -> dict[str, Any] | None:
        sensor = self.sensors.get(device_id)
        if sensor is None:
            return None
        return {
            **sensor,
            "state": self.sensor_state(device_id),
            "trend": list(self.trends.get(device_id, ())),
        }

    def sensor_snapshots(self) -> list[dict[str, Any]]:
        return [
            snapshot
            for device_id in sorted(self.sensors)
            if (snapshot := self.sensor_snapshot(device_id)) is not None
        ]

    def sensor_update(self, device_id: str) -> dict[str, Any] | None:
        snapshot = self.sensor_snapshot(device_id)
        if snapshot is None:
            return None
        snapshot.pop("trend", None)
        return snapshot

    def incident_snapshot(self, incident: Incident) -> dict[str, Any]:
        return {
            "incident_id": incident.incident_id,
            "device_id": incident.device_id,
            "category": incident.category.value,
            "state": incident.state.value,
            "first_seen": incident.first_seen,
            "last_seen": incident.last_seen,
            "affected_reading_count": incident.affected_reading_count,
            "detectors": sorted(incident.detectors),
            "peak_severity": incident.peak_severity,
            "peak_observed_value": incident.peak_observed_value,
            "confidence": incident.confidence,
            "decision": incident.decision,
            "reason_codes": incident.reason_codes,
            "retrieved_incident_ids": incident.retrieved_incident_ids,
            "retrieval_top_distance": incident.retrieval_top_distance,
            "retrieval_second_distance": incident.retrieval_second_distance,
            "retrieval_evidence": self.retrieval_evidence.get(incident.incident_id, []),
            "review": self.reviews.get(incident.incident_id),
            "acknowledged": incident.incident_id in self.acknowledged,
            "manually_resolved": incident.incident_id in self.manually_resolved,
        }

    def incident_snapshots(self) -> list[dict[str, Any]]:
        ordered = sorted(
            self.incidents.values(), key=lambda incident: incident.last_seen, reverse=True
        )
        return [self.incident_snapshot(incident) for incident in ordered]

    def sensor_state(self, device_id: str) -> str:
        latest = self.sensors.get(device_id)
        if latest is None:
            return "offline"
        active = [
            incident
            for incident in self.incidents.values()
            if incident.device_id == device_id
            and incident.state is not IncidentState.RESOLVED
        ]
        if any(
            incident.state in {IncidentState.RECOMMENDED, IncidentState.ESCALATED}
            and incident.category is IncidentCategory.EQUIPMENT_CONDITION
            for incident in active
        ):
            return "critical"
        if active or latest["vibration"] is None:
            return "watch"
        return "normal"

    async def record_reading(self, reading: SensorReading) -> None:
        self.sensors[reading.device_id] = {
            "event_id": reading.event_id,
            "sequence_number": reading.sequence_number,
            "device_id": reading.device_id,
            "asset_id": reading.asset_id or reading.device_id,
            "equipment_type": reading.equipment_type,
            "equipment_name": reading.equipment_name
            or reading.equipment_type.replace("_", " ").title(),
            "area": reading.area or "Unassigned area",
            "sensor_type": reading.sensor_type,
            "unit": reading.unit,
            "timestamp": reading.timestamp,
            "temperature": reading.temperature,
            "humidity": reading.humidity,
            "vibration": reading.vibration,
        }
        trend = self.trends.setdefault(
            reading.device_id, deque(maxlen=self.trend_size)
        )
        trend.append(reading.vibration)
        self.last_reading_at = time.time()
        await self.publish("sensor.updated", self.sensor_update(reading.device_id))

    async def record_detector_event(self, event: AnomalyEvent) -> None:
        payload = {
            "timestamp": event.timestamp,
            "device_id": event.device_id,
            "detector": event.detector,
            "description": event.description,
            "severity": event.severity,
            "context": event.context,
        }
        self.add_activity("detector.triggered", payload)
        await self.publish("detector.triggered", payload, priority=True)

    async def record_incident(self, incident: Incident, event: str = "incident.updated") -> None:
        self.incidents[incident.incident_id] = incident
        payload = self.incident_snapshot(incident)
        self.add_activity(event, payload)
        await self.publish(event, payload, priority=True)
        sensor = self.sensor_update(incident.device_id)
        if sensor is not None:
            await self.publish("sensor.updated", sensor)

    def add_activity(self, event: str, payload: dict[str, Any]) -> None:
        self.activity.appendleft(
            {"event": event, "recorded_at": time.time(), "data": payload}
        )

    async def set_stream_status(self, status: str, error: str | None = None) -> None:
        if status == self.stream_status and error == self.stream_error:
            return
        self.stream_status = status
        self.stream_error = error
        payload = {"status": status, "error": error, "updated_at": time.time()}
        self.add_activity("stream.status", payload)
        await self.publish("stream.status", payload, priority=True)

    async def publish(
        self, event: str, data: Any, *, priority: bool = False
    ) -> None:
        self._event_id += 1
        message = {"id": self._event_id, "event": event, "data": data}
        for queue in tuple(self._clients):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                if not priority:
                    continue
                with suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
                with suppress(asyncio.QueueFull):
                    queue.put_nowait(message)

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(
            maxsize=self.client_queue_size
        )
        self._clients.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._clients.discard(queue)


class StreamRuntime:
    def __init__(self, host: str = "127.0.0.1", port: int = 9999, database: RuntimeDatabase | None | object = _DEFAULT_DATABASE, retriever=None):
        self.host = host
        self.port = port
        self.store = RuntimeStore()
        self.detector_sets: dict[str, DeviceDetectorSet] = {}
        self.aggregator = IncidentAggregator()
        self.policy = self._build_policy(self.store.policy_config)
        if database is _DEFAULT_DATABASE:
            self.database = RuntimeDatabase(Path(os.getenv("RUNTIME_DB_PATH", "data/runtime.sqlite3")))
        else:
            self.database = database
        if self.database and (saved_policy := self.database.load_policy()):
            self.store.policy_config = PolicyConfig.model_validate(saved_policy)
            self.policy = self._build_policy(self.store.policy_config)
        self.retriever = retriever
        self._retriever_attempted = retriever is not None
        restored = self.database.load_incidents() if self.database else []
        self.store.incidents = {incident.incident_id: incident for incident in restored}
        if self.database:
            self.store.retrieval_evidence = self.database.load_retrieval_evidence()
            self.store.reviews = self.database.load_reviews()
        self.aggregator.restore(restored)

    async def run(self) -> None:
        await self.store.set_stream_status("connecting")
        async for reading in stream_readings(
            self.host, self.port, on_status=self.store.set_stream_status
        ):
            await self.process_reading(reading)

    async def process_reading(self, reading: SensorReading) -> None:
        await self.store.record_reading(reading)
        if reading.device_id not in self.detector_sets:
            self.detector_sets[reading.device_id] = DeviceDetectorSet(
                max_staleness_seconds=30.0
            )
            baseline = self.database.load_baseline(reading.device_id) if self.database else None
            if baseline is not None:
                self.detector_sets[reading.device_id].restore_baseline(*baseline)
        detectors = self.detector_sets[reading.device_id]

        for resolved in self.aggregator.resolve_quiet(
            reading.device_id, reading.timestamp
        ):
            if self.database:
                self.database.save_incident(resolved)
            await self.store.record_incident(resolved, "incident.resolved")

        events = detectors.check(reading)
        if self.database:
            self.database.save_baseline(
                reading.device_id, detectors.baseline_values(), reading.sequence_number, reading.timestamp
            )
        for event in events:
            await self.store.record_detector_event(event)
            incident = self.aggregator.aggregate(event)
            matches = self._retrieve(event) if incident.category is IncidentCategory.EQUIPMENT_CONDITION else None
            if matches is not None:
                incident.retrieved_incident_ids = [match.incident_id for match in matches]
                incident.retrieval_top_distance = matches[0].distance if matches else None
                incident.retrieval_second_distance = matches[1].distance if len(matches) > 1 else None
                evidence = [{"incident_id": match.incident_id, "distance": match.distance, "verified": match.metadata.get("verified"), "source_url": match.metadata.get("source_url"), "summary": match.retrieval_text} for match in matches]
                self.store.retrieval_evidence[incident.incident_id] = evidence
                if self.database:
                    self.database.save_retrieval_evidence(incident.incident_id, evidence)
            result = self.policy.evaluate(incident, matches)
            self.aggregator.apply_decision(incident, result)
            if self.database:
                self.database.save_incident(incident)
            await self.store.record_incident(incident)

    def _retrieve(self, event: AnomalyEvent):
        if self.retriever is None and not self._retriever_attempted:
            self._retriever_attempted = True
            try:
                self.retriever = build_incident_retriever()
            except Exception:
                return []
        if self.retriever is None:
            return []
        try:
            return self.retriever.search(RetrievalQuery(
                text=f"{event.detector}: {event.description}",
                equipment_type=event.reading.equipment_type,
                sensor_type=event.reading.sensor_type,
                incident_category=IncidentCategory.EQUIPMENT_CONDITION.value,
            ))
        except Exception:
            return []

    async def update_policy(self, config: PolicyConfig) -> dict[str, Any]:
        policy = self._build_policy(config)
        self.policy = policy
        self.store.policy_config = config
        if self.database:
            self.database.save_policy(config.model_dump())
        for incident in self.store.incidents.values():
            if incident.state is IncidentState.RESOLVED:
                continue
            result = self.policy.evaluate(incident)
            self.aggregator.apply_decision(incident, result)
            if self.database:
                self.database.save_incident(incident)
            await self.store.record_incident(incident)
        payload = config.model_dump()
        self.store.add_activity("policy.updated", payload)
        await self.store.publish("policy.updated", payload, priority=True)
        return payload

    async def acknowledge(self, incident_id: str) -> dict[str, Any] | None:
        incident = self.store.incidents.get(incident_id)
        if incident is None:
            return None
        self.store.acknowledged.add(incident_id)
        if self.database:
            self.database.save_incident(incident)
        await self.store.record_incident(incident)
        return self.store.incident_snapshot(incident)

    async def resolve(self, incident_id: str) -> dict[str, Any] | None:
        incident = self.store.incidents.get(incident_id)
        if incident is None:
            return None
        incident.state = IncidentState.RESOLVED
        if "operator_resolved" not in incident.reason_codes:
            incident.reason_codes.append("operator_resolved")
        self.store.manually_resolved.add(incident_id)
        if self.database:
            self.database.save_incident(incident)
        await self.store.record_incident(incident, "incident.resolved")
        return self.store.incident_snapshot(incident)

    async def review(self, incident_id: str, request: ReviewRequest) -> dict[str, Any] | None:
        incident = self.store.incidents.get(incident_id)
        if incident is None:
            return None
        review = {"outcome": request.outcome, "notes": request.notes, "reviewed_at": time.time()}
        self.store.reviews[incident_id] = review
        if self.database:
            self.database.save_review(incident_id, request.outcome, request.notes, review["reviewed_at"])
        await self.store.record_incident(incident, "incident.reviewed")
        return self.store.incident_snapshot(incident)

    @staticmethod
    def _build_policy(config: PolicyConfig) -> DecisionPolicy:
        return DecisionPolicy(
            detector_weights={
                "spike": config.spike_weight,
                "drift": config.drift_weight,
            },
            monitor_threshold=config.monitor_threshold,
            recommend_threshold=config.recommend_threshold,
            persistence_step=config.persistence_step,
            max_persistence_bonus=config.max_persistence_bonus,
            data_quality_min_readings=config.data_quality_min_readings,
        )
