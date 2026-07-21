import unittest

from iot_stream.incidents.aggregator import IncidentAggregator
from iot_stream.incidents.models import Incident, IncidentCategory, IncidentState
from iot_stream.incidents.policy import Decision, DecisionPolicy, DecisionResult
from test.helpers import anomaly


class IncidentAggregatorTests(unittest.TestCase):
    def test_aggregates_same_device_and_category(self):
        aggregator = IncidentAggregator()
        first = aggregator.aggregate(anomaly("spike", 1))
        second = aggregator.aggregate(anomaly("drift", 2))
        self.assertIs(first, second)
        self.assertEqual(second.detectors, {"spike", "drift"})
        self.assertEqual(second.affected_reading_count, 2)
        self.assertEqual(second.state, IncidentState.INVESTIGATING)

    def test_never_merges_data_quality_with_equipment(self):
        aggregator = IncidentAggregator()
        equipment = aggregator.aggregate(anomaly("spike", 1))
        quality = aggregator.aggregate(anomaly("sequence_gap", 2))
        self.assertNotEqual(equipment.incident_id, quality.incident_id)
        self.assertEqual(quality.category, IncidentCategory.DATA_QUALITY)

    def test_quiet_period_and_notification_cooldown(self):
        aggregator = IncidentAggregator(
            quiet_period_seconds=10, notification_cooldown_seconds=20
        )
        incident = aggregator.aggregate(anomaly("spike", 1))
        self.assertTrue(aggregator.notification_due(incident, 1))
        self.assertFalse(aggregator.notification_due(incident, 10))
        self.assertEqual(aggregator.resolve_quiet("sensor-1", 5), [])
        self.assertEqual(aggregator.resolve_quiet("sensor-1", 11), [incident])
        self.assertEqual(incident.state, IncidentState.RESOLVED)


class DecisionPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = DecisionPolicy()

    @staticmethod
    def incident(detectors, count=1, category=IncidentCategory.EQUIPMENT_CONDITION):
        return Incident(
            incident_id="INC-1",
            device_id="sensor-1",
            category=category,
            state=IncidentState.INVESTIGATING,
            first_seen=1.0,
            last_seen=2.0,
            affected_reading_count=count,
            detectors=set(detectors),
        )

    def test_weighted_agreement_recommends_only_with_both_detectors(self):
        partial = self.policy.evaluate(self.incident({"spike"}))
        strong = self.policy.evaluate(self.incident({"spike", "drift"}, count=2))
        self.assertEqual(partial.decision, Decision.MONITOR)
        self.assertEqual(strong.decision, Decision.RECOMMEND)
        self.assertGreaterEqual(strong.confidence, 0.75)

    def test_unknown_detector_has_zero_weight_and_escalates(self):
        result = self.policy.evaluate(self.incident({"mystery"}))
        self.assertEqual(result.decision, Decision.ESCALATE)
        self.assertEqual(result.confidence, 0.0)

    def test_persistence_bonus_is_bounded(self):
        result = self.policy.evaluate(self.incident({"spike"}, count=100))
        self.assertAlmostEqual(result.confidence, 0.60)

    def test_data_quality_requires_sustained_evidence(self):
        first = self.policy.evaluate(self.incident({"sequence_gap"}, category=IncidentCategory.DATA_QUALITY))
        sustained = self.policy.evaluate(self.incident({"sequence_gap"}, count=2, category=IncidentCategory.DATA_QUALITY))
        self.assertEqual(first.decision, Decision.MONITOR)
        self.assertEqual(sustained.decision, Decision.DATA_QUALITY_ALERT)

    def test_recommendation_result_cannot_be_below_threshold(self):
        with self.assertRaises(ValueError):
            DecisionResult(Decision.RECOMMEND, 0.5, ("unsafe",))


if __name__ == "__main__":
    unittest.main()
