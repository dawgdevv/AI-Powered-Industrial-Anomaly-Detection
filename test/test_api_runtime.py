import unittest

from httpx import ASGITransport, AsyncClient

from iot_stream.api.main import create_app
from iot_stream.api.models import PolicyConfig
from iot_stream.api.runtime import RuntimeStore, StreamRuntime
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
    async def test_policy_update_re_evaluates_open_incident(self):
        runtime = StreamRuntime()
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

    async def test_acknowledge_and_resolve_are_runtime_actions(self):
        runtime = StreamRuntime()
        incident = runtime.aggregator.aggregate(anomaly("spike", 1))
        runtime.store.incidents[incident.incident_id] = incident
        acknowledged = await runtime.acknowledge(incident.incident_id)
        resolved = await runtime.resolve(incident.incident_id)
        self.assertTrue(acknowledged["acknowledged"])
        self.assertEqual(resolved["state"], "RESOLVED")
        self.assertTrue(resolved["manually_resolved"])


class ApiRouteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.runtime = StreamRuntime()
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

    async def test_incident_actions_and_missing_resources(self):
        incident = self.runtime.aggregator.aggregate(anomaly("spike", 1))
        self.runtime.store.incidents[incident.incident_id] = incident
        acknowledged = await self.client.post(
            f"/api/incidents/{incident.incident_id}/acknowledge"
        )
        resolved = await self.client.post(f"/api/incidents/{incident.incident_id}/resolve")
        self.assertTrue(acknowledged.json()["acknowledged"])
        self.assertEqual(resolved.json()["state"], "RESOLVED")
        self.assertEqual((await self.client.get("/api/sensors/missing")).status_code, 404)


if __name__ == "__main__":
    unittest.main()
