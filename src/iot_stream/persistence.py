"""Small SQLite state store for restart-safe baselines and incident decisions."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from iot_stream.incidents.models import Incident, IncidentCategory, IncidentState


class RuntimeDatabase:
    # ponytail: SQLite is enough for one local process; use Postgres when workers scale out.
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS baselines (
              device_id TEXT PRIMARY KEY, values_json TEXT NOT NULL,
              last_sequence INTEGER, last_timestamp REAL, updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS incidents (
              incident_id TEXT PRIMARY KEY, device_id TEXT NOT NULL, category TEXT NOT NULL,
              state TEXT NOT NULL, first_seen REAL NOT NULL, last_seen REAL NOT NULL,
              affected_reading_count INTEGER NOT NULL, detectors_json TEXT NOT NULL,
              peak_severity TEXT NOT NULL, peak_observed_value REAL, confidence REAL NOT NULL,
              decision TEXT, reason_codes_json TEXT NOT NULL, retrieved_ids_json TEXT NOT NULL,
              retrieval_top_distance REAL, retrieval_second_distance REAL,
              last_notified_at REAL, reading_ids_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS runtime_policy (
              id INTEGER PRIMARY KEY CHECK (id = 1), policy_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS incident_retrieval_evidence (
              incident_id TEXT PRIMARY KEY, evidence_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS review_outcomes (
              incident_id TEXT PRIMARY KEY, outcome TEXT NOT NULL, notes TEXT NOT NULL,
              reviewed_at REAL NOT NULL, knowledge_enriched INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS incident_workflow (
              incident_id TEXT PRIMARY KEY, acknowledged_at REAL NOT NULL,
              healthy_reading_count INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS agent_assessments (
              incident_id TEXT PRIMARY KEY, assessment_json TEXT NOT NULL
            );
            """
        )
        try:
            self.connection.execute(
                "ALTER TABLE review_outcomes ADD COLUMN knowledge_enriched INTEGER NOT NULL DEFAULT 0"
            )
        except sqlite3.OperationalError:
            pass
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def save_policy(self, policy: dict[str, object]) -> None:
        self.connection.execute(
            "INSERT INTO runtime_policy VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET policy_json=excluded.policy_json",
            (json.dumps(policy),),
        )
        self.connection.commit()

    def load_policy(self) -> dict[str, object] | None:
        row = self.connection.execute(
            "SELECT policy_json FROM runtime_policy WHERE id=1"
        ).fetchone()
        return json.loads(row["policy_json"]) if row else None

    def save_retrieval_evidence(self, incident_id: str, evidence: list[dict[str, object]]) -> None:
        self.connection.execute(
            "INSERT INTO incident_retrieval_evidence VALUES (?, ?) ON CONFLICT(incident_id) DO UPDATE SET evidence_json=excluded.evidence_json",
            (incident_id, json.dumps(evidence)),
        )
        self.connection.commit()

    def load_retrieval_evidence(self) -> dict[str, list[dict[str, object]]]:
        rows = self.connection.execute("SELECT * FROM incident_retrieval_evidence").fetchall()
        return {row["incident_id"]: json.loads(row["evidence_json"]) for row in rows}

    def save_review(self, incident_id: str, outcome: str, notes: str, reviewed_at: float, knowledge_enriched: bool = False) -> None:
        self.connection.execute(
            "INSERT INTO review_outcomes VALUES (?, ?, ?, ?, ?) ON CONFLICT(incident_id) DO UPDATE SET outcome=excluded.outcome,notes=excluded.notes,reviewed_at=excluded.reviewed_at,knowledge_enriched=excluded.knowledge_enriched",
            (incident_id, outcome, notes, reviewed_at, int(knowledge_enriched)),
        )
        self.connection.commit()

    def load_reviews(self) -> dict[str, dict[str, object]]:
        rows = self.connection.execute("SELECT * FROM review_outcomes").fetchall()
        return {row["incident_id"]: {"outcome": row["outcome"], "notes": row["notes"], "reviewed_at": row["reviewed_at"], "knowledge_enriched": bool(row["knowledge_enriched"])} for row in rows}

    def save_workflow(self, incident_id: str, acknowledged_at: float, healthy_reading_count: int) -> None:
        self.connection.execute(
            "INSERT INTO incident_workflow VALUES (?, ?, ?) ON CONFLICT(incident_id) DO UPDATE SET acknowledged_at=excluded.acknowledged_at,healthy_reading_count=excluded.healthy_reading_count",
            (incident_id, acknowledged_at, healthy_reading_count),
        )
        self.connection.commit()

    def load_workflows(self) -> dict[str, dict[str, float | int]]:
        rows = self.connection.execute("SELECT * FROM incident_workflow").fetchall()
        return {row["incident_id"]: {"started_at": row["acknowledged_at"], "healthy_reading_count": row["healthy_reading_count"]} for row in rows}

    def clear_workflow(self, incident_id: str) -> None:
        self.connection.execute("DELETE FROM incident_workflow WHERE incident_id=?", (incident_id,))
        self.connection.commit()

    def save_agent_assessment(self, incident_id: str, assessment: dict[str, object]) -> None:
        self.connection.execute(
            "INSERT INTO agent_assessments VALUES (?, ?) ON CONFLICT(incident_id) DO UPDATE SET assessment_json=excluded.assessment_json",
            (incident_id, json.dumps(assessment)),
        )
        self.connection.commit()

    def load_agent_assessments(self) -> dict[str, dict[str, object]]:
        rows = self.connection.execute("SELECT * FROM agent_assessments").fetchall()
        return {row["incident_id"]: json.loads(row["assessment_json"]) for row in rows}

    def save_baseline(
        self, device_id: str, values: list[float], last_sequence: int, last_timestamp: float
    ) -> None:
        self.connection.execute(
            "INSERT INTO baselines VALUES (?, ?, ?, ?, ?) ON CONFLICT(device_id) DO UPDATE SET values_json=excluded.values_json, last_sequence=excluded.last_sequence, last_timestamp=excluded.last_timestamp, updated_at=excluded.updated_at",
            (device_id, json.dumps(values), last_sequence, last_timestamp, last_timestamp),
        )
        self.connection.commit()

    def load_baseline(self, device_id: str) -> tuple[list[float], int | None, float | None] | None:
        row = self.connection.execute("SELECT * FROM baselines WHERE device_id=?", (device_id,)).fetchone()
        if row is None:
            return None
        return json.loads(row["values_json"]), row["last_sequence"], row["last_timestamp"]

    def save_incident(self, incident: Incident) -> None:
        self.connection.execute(
            "INSERT INTO incidents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(incident_id) DO UPDATE SET state=excluded.state,last_seen=excluded.last_seen,affected_reading_count=excluded.affected_reading_count,detectors_json=excluded.detectors_json,peak_severity=excluded.peak_severity,peak_observed_value=excluded.peak_observed_value,confidence=excluded.confidence,decision=excluded.decision,reason_codes_json=excluded.reason_codes_json,retrieved_ids_json=excluded.retrieved_ids_json,retrieval_top_distance=excluded.retrieval_top_distance,retrieval_second_distance=excluded.retrieval_second_distance,last_notified_at=excluded.last_notified_at,reading_ids_json=excluded.reading_ids_json",
            (incident.incident_id, incident.device_id, incident.category.value, incident.state.value, incident.first_seen, incident.last_seen, incident.affected_reading_count, json.dumps(sorted(incident.detectors)), incident.peak_severity, incident.peak_observed_value, incident.confidence, incident.decision, json.dumps(incident.reason_codes), json.dumps(incident.retrieved_incident_ids), incident.retrieval_top_distance, incident.retrieval_second_distance, incident.last_notified_at, json.dumps(sorted(incident._reading_ids))),
        )
        self.connection.commit()

    def load_incidents(self) -> list[Incident]:
        rows = self.connection.execute("SELECT * FROM incidents ORDER BY last_seen DESC").fetchall()
        return [Incident(
            incident_id=row["incident_id"], device_id=row["device_id"], category=IncidentCategory(row["category"]), state=IncidentState(row["state"]), first_seen=row["first_seen"], last_seen=row["last_seen"], affected_reading_count=row["affected_reading_count"], detectors=set(json.loads(row["detectors_json"])), peak_severity=row["peak_severity"], peak_observed_value=row["peak_observed_value"], confidence=row["confidence"], decision=row["decision"], reason_codes=json.loads(row["reason_codes_json"]), retrieved_incident_ids=json.loads(row["retrieved_ids_json"]), retrieval_top_distance=row["retrieval_top_distance"], retrieval_second_distance=row["retrieval_second_distance"], last_notified_at=row["last_notified_at"], _reading_ids=set(json.loads(row["reading_ids_json"])),
        ) for row in rows]
