import unittest

from iot_stream.agent import EXPORTED_TOOLS, IncidentMonitoringAgent
from iot_stream.incidents.models import Incident, IncidentCategory, IncidentState
from iot_stream.pipeline.detectors import DeviceDetectorSet
from test.helpers import reading


class AgentTests(unittest.TestCase):
    def test_agent_exports_only_read_only_context_tools(self):
        self.assertEqual(
            [tool.name for tool in EXPORTED_TOOLS],
            ["get_incident_context", "get_retrieved_precedents", "get_recovery_status"],
        )

    def test_agent_abstains_without_verified_precedent(self):
        incident = Incident(
            incident_id="INC-1", device_id="sensor-1",
            category=IncidentCategory.EQUIPMENT_CONDITION, state=IncidentState.INVESTIGATING,
            first_seen=1, last_seen=1, detectors={"spike"}, affected_reading_count=1,
        )
        assessment = IncidentMonitoringAgent().assess(incident, reading(1, vibration=0.8), [])
        self.assertTrue(assessment.abstained)
        self.assertEqual(assessment.abstention_reason, "no_verified_precedent")
        self.assertTrue(assessment.model_fallback)

    def test_drifting_sensor_is_not_counted_as_healthy_during_alert_cooldown(self):
        detectors = DeviceDetectorSet()
        latest = None
        for sequence in range(1, 41):
            latest = reading(sequence, vibration=0.2 + sequence * 0.02)
            detectors.check(latest)
        self.assertFalse(detectors.equipment_is_healthy(latest))

    def test_agent_keeps_evidence_until_retrieval_and_stable_recovery_complete(self):
        incident = Incident(
            incident_id="INC-1", device_id="sensor-1",
            category=IncidentCategory.EQUIPMENT_CONDITION, state=IncidentState.INVESTIGATING,
            first_seen=1, last_seen=1, detectors={"spike"}, affected_reading_count=1,
        )
        agent = IncidentMonitoringAgent(healthy_readings_to_resolve=5, recovery_stability_seconds=2)
        workflow: dict[str, object] = {}
        agent.activate(incident, workflow)
        for sequence in range(1, 6):
            update = agent.observe(incident, workflow, reading(sequence), [], knowledge_ready=False)
        self.assertFalse(update.resolved)
        self.assertEqual(workflow["recovery_state"], "awaiting_knowledge")

        update = agent.observe(incident, workflow, reading(6), [], knowledge_ready=True)
        self.assertTrue(update.resolved)
        self.assertEqual(workflow["recovery_state"], "resolved")


if __name__ == "__main__":
    unittest.main()
