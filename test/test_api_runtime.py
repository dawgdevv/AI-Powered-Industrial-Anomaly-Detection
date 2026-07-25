import asyncio
import unittest

from httpx import ASGITransport, AsyncClient

from iot_stream.api.main import create_app
from iot_stream.api.models import PolicyConfig
from iot_stream.api.runtime import RuntimeStore, StreamRuntime
from iot_stream.incidents.models import IncidentCategory, IncidentState
from iot_stream.knowledge.models import RetrievalMatch
from test.helpers import anomaly, reading


class RuntimeStoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_sensor_history_is_bounded_and_live_update_is_compact(self):
        store = RuntimeStore(trend_size=3)
        for sequence in range(1, 6):
            await store.record_reading(reading(sequence, vibration=sequence / 10))
        snapshot = store.sensor_snapshot("sensor-1")
        self.assertEqual(snapshot["trend"], [0.3, 0.4, 0.5])
        self.assertEqual(snapshot["asset_id"], "P-101")
        self.assertEqual(snapshot["equipment_name"], "Raw Water Intake Pump")
        self.assertEqual(snapshot["area"], "Intake Station")
        self.assertNotIn("trend", store.sensor_update("sensor-1"))

    async def test_priority_event_survives_full_client_queue(self):
        store = RuntimeStore(client_queue_size=1)
        queue = store.subscribe()
        await store.publish("sensor.updated", {"value": 1})
        await store.publish("incident.updated", {"value": 2}, priority=True)
        self.assertEqual((await queue.get())["event"], "incident.updated")


class StreamRuntimeTests(unittest.IsolatedAsyncioTestCase):
    class VerifiedRetriever:
        def __init__(self):
            self.query = None

        def search(self, _query):
            self.query = _query
            return [RetrievalMatch(
                incident_id="WT-INC-001", retrieval_text="Water-treatment intake pump bearing misalignment scenario.",
                metadata={"verified": True, "source_url": "", "fault_family": "bearing_misalignment", "source_kind": "water_treatment_simulation"},
                distance=0.1,
            )]

    async def test_policy_update_re_evaluates_open_incident(self):
        runtime = StreamRuntime(database=None)
        incident = runtime.aggregator.aggregate(anomaly("spike", 1))
        runtime.store.incidents[incident.incident_id] = incident
        updated = await runtime.update_policy(PolicyConfig(
            spike_weight=1,
            drift_weight=0,
            monitor_threshold=0.4,
            recommend_threshold=0.75,
        ))
        self.assertEqual(updated["spike_weight"], 1)
        self.assertEqual(incident.decision, "RECOMMEND")

    async def test_agent_resolves_after_five_healthy_readings(self):
        runtime = StreamRuntime(database=None)
        incident = runtime.aggregator.aggregate(anomaly("spike", 1))
        runtime.store.incidents[incident.incident_id] = incident
        runtime._activate_agent(incident)
        for sequence in range(2, 7):
            await runtime._agent_observe_recovery(reading(sequence, vibration=0.2), [])
        snapshot = runtime.store.incident_snapshot(incident)
        self.assertEqual(snapshot["state"], "RESOLVED")
        self.assertTrue(snapshot["automatically_resolved"])
        self.assertEqual(snapshot["healthy_reading_count"], 5)

    async def test_live_feed_activates_assesses_and_auto_resolves(self):
        retriever = self.VerifiedRetriever()
        runtime = StreamRuntime(database=None, retriever=retriever)
        for sequence in range(1, 10):
            await runtime.process_reading(reading(sequence, vibration=0.2))
        await runtime.process_reading(reading(10, vibration=0.8))
        await asyncio.gather(*runtime._retrieval_tasks.values())
        active = next(
            incident for incident in runtime.store.incidents.values()
            if incident.category is IncidentCategory.EQUIPMENT_CONDITION
        )
        self.assertNotEqual(active.state, IncidentState.RESOLVED)
        self.assertEqual(runtime.store.agent_assessments[active.incident_id]["likely_fault"], "bearing misalignment")
        self.assertIn("centrifugal_pump", retriever.query.text)
        self.assertIn("vibration", retriever.query.text)
        self.assertIn("temperature", retriever.query.text)

        for sequence in range(11, 16):
            await runtime.process_reading(reading(sequence, vibration=0.2))
        snapshot = runtime.store.incident_snapshot(active)
        self.assertEqual(snapshot["state"], "RESOLVED")
        self.assertTrue(snapshot["automatically_resolved"])


class ApiRouteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.runtime = StreamRuntime(database=None)
        self.client = AsyncClient(
            transport=ASGITransport(app=create_app(self.runtime, start_worker=False)),
            base_url="http://test",
        )

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_snapshot_and_policy_routes(self):
        self.assertEqual((await self.client.get("/api/sensors")).status_code, 200)
        self.assertEqual((await self.client.get("/api/incidents")).json(), [])
        self.assertEqual((await self.client.get("/api/policy")).json()["spike_weight"], 0.45)
        self.assertEqual(
            (await self.client.get("/api/health")).json()["configured_fleet_size"], 6
        )
        services = (await self.client.get("/api/health")).json()["services"]
        self.assertEqual(
            {service["id"] for service in services},
            {"stream", "detectors", "incidents", "knowledge", "agent", "policy", "observability"},
        )

    async def test_valid_policy_update_and_invalid_update(self):
        valid = {
            "spike_weight": 0.4,
            "drift_weight": 0.6,
            "monitor_threshold": 0.35,
            "recommend_threshold": 0.8,
            "persistence_step": 0.05,
            "max_persistence_bonus": 0.15,
            "data_quality_min_readings": 2,
        }
        self.assertEqual((await self.client.put("/api/policy", json=valid)).status_code, 200)
        invalid = {**valid, "spike_weight": 0, "drift_weight": 0}
        self.assertEqual((await self.client.put("/api/policy", json=invalid)).status_code, 422)
        self.assertEqual((await self.client.get("/api/policy")).json()["spike_weight"], 0.4)

    async def test_operator_reports_are_the_only_incident_action(self):
        incident = self.runtime.aggregator.aggregate(anomaly("spike", 1))
        self.runtime.store.incidents[incident.incident_id] = incident
        report = await self.client.post(
            f"/api/incidents/{incident.incident_id}/review",
            json={"outcome": "false_alarm", "notes": "Checked coupling; no defect found."},
        )
        self.assertEqual(report.status_code, 200)
        self.assertEqual(report.json()["review"]["outcome"], "false_alarm")
        self.assertEqual((await self.client.post(f"/api/incidents/{incident.incident_id}/acknowledge")).status_code, 404)
        self.assertEqual((await self.client.post(f"/api/incidents/{incident.incident_id}/resolve")).status_code, 404)
        self.assertEqual((await self.client.get("/api/sensors/missing")).status_code, 404)


if __name__ == "__main__":
    unittest.main()
