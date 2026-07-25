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


if __name__ == "__main__":
    unittest.main()
