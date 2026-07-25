import asyncio
import tempfile
import unittest
from pathlib import Path

from iot_stream.api.models import PolicyConfig
from iot_stream.api.runtime import StreamRuntime
from iot_stream.incidents.models import Incident, IncidentCategory, IncidentState
from iot_stream.incidents.policy import Decision, DecisionPolicy
from iot_stream.knowledge.models import RetrievalMatch
from iot_stream.persistence import RuntimeDatabase


class PersistenceAndRetrievalTests(unittest.TestCase):
    def test_sqlite_restores_baseline_and_incident_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            database = RuntimeDatabase(Path(directory) / "runtime.sqlite3")
            database.save_baseline("sensor-1", [0.2, 0.21], 9, 10.0)
            incident = Incident(
                incident_id="INC-000001", device_id="sensor-1",
                category=IncidentCategory.EQUIPMENT_CONDITION,
                state=IncidentState.RECOMMENDED, first_seen=1.0, last_seen=2.0,
                detectors={"spike", "drift"}, confidence=0.9, decision="RECOMMEND",
                retrieved_incident_ids=["KB-INC-0001"], retrieval_top_distance=0.12,
            )
            database.save_incident(incident)
            self.assertEqual(database.load_baseline("sensor-1"), ([0.2, 0.21], 9, 10.0))
            restored = database.load_incidents()[0]
            self.assertEqual(restored.retrieved_incident_ids, ["KB-INC-0001"])
            self.assertEqual(restored.retrieval_top_distance, 0.12)
            database.close()

    def test_verified_retrieval_is_required_when_matches_are_supplied(self):
        incident = Incident(
            incident_id="INC-000001", device_id="sensor-1",
            category=IncidentCategory.EQUIPMENT_CONDITION,
            state=IncidentState.INVESTIGATING, first_seen=1.0, last_seen=2.0,
            affected_reading_count=2, detectors={"spike", "drift"},
        )
        policy = DecisionPolicy()
        self.assertEqual(policy.evaluate(incident, []).decision, Decision.ESCALATE)
        match = RetrievalMatch("KB-INC-0001", "bearing wear", {"verified": True}, 0.1)
        self.assertEqual(policy.evaluate(incident, [match]).decision, Decision.RECOMMEND)

    def test_runtime_policy_survives_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime.sqlite3"
            runtime = StreamRuntime(database=RuntimeDatabase(path))
            config = PolicyConfig(spike_weight=0.7, drift_weight=0.3, recommend_threshold=0.9)
            asyncio.run(runtime.update_policy(config))
            runtime.database.close()

            restarted = StreamRuntime(database=RuntimeDatabase(path))
            self.assertEqual(restarted.store.policy_config, config)
            restarted.database.close()


if __name__ == "__main__":
    unittest.main()
