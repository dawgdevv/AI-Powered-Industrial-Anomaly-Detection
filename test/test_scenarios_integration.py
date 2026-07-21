import unittest

from simulator.producer import build_sensors, generate_scenario_readings
from simulator.types import SimulatorConfig

from iot_stream.incidents import Decision, DecisionPolicy, IncidentAggregator
from iot_stream.pipeline.detectors import DeviceDetectorSet
from iot_stream.schemas import SensorReading


class DeterministicScenarioTests(unittest.TestCase):
    def test_same_seed_and_scenario_are_identical(self):
        first = generate_scenario_readings("known_fault", 42, 50)
        second = generate_scenario_readings("known_fault", 42, 50)
        self.assertEqual(first, second)

    def test_different_seeds_change_sensor_environment(self):
        first = generate_scenario_readings("novel_fault", 1, 5)
        second = generate_scenario_readings("novel_fault", 2, 5)
        self.assertNotEqual(first, second)

    def test_known_fault_is_bounded_and_only_affects_sensor_one(self):
        config = SimulatorConfig(
            num_devices=4, seed=42, scenario="known_fault", emit_interval=0.1
        )
        sensors = build_sensors(config, timestamp_origin=1_700_000_000.0)
        readings = [[sensor.read() for _ in range(150)] for sensor in sensors]
        self.assertLessEqual(max(item.vibration for item in readings[0]), 3.5)
        self.assertTrue(any(item.fault_active for item in readings[0]))
        self.assertTrue(all(not item.fault_active for fleet in readings[1:] for item in fleet))
        self.assertTrue(all(0.28 <= item.vibration <= 0.32 for fleet in readings[1:] for item in fleet))
        self.assertTrue(all(0.28 <= item.vibration <= 0.32 for item in readings[0][-50:]))


class MilestoneIntegrationTests(unittest.TestCase):
    @staticmethod
    def run_scenario(name: str, count: int):
        detectors = DeviceDetectorSet()
        aggregator = IncidentAggregator()
        policy = DecisionPolicy()
        results = []
        for simulated in generate_scenario_readings(name, 7, count):
            reading = SensorReading.from_dict(simulated.to_dict())
            for event in detectors.check(reading):
                incident = aggregator.aggregate(event)
                result = policy.evaluate(incident)
                aggregator.apply_decision(incident, result)
                results.append((event, incident, result))
        return results

    def test_known_fault_reaches_recommendation(self):
        results = self.run_scenario("known_fault", 60)
        detector_names = {event.detector for event, _incident, _result in results}
        decisions = {result.decision for _event, _incident, result in results}
        self.assertIn("spike", detector_names)
        self.assertIn("drift", detector_names)
        self.assertIn(Decision.RECOMMEND, decisions)

    def test_novel_fault_does_not_recommend(self):
        results = self.run_scenario("novel_fault", 30)
        decisions = {result.decision for _event, _incident, result in results}
        self.assertTrue(decisions)
        self.assertNotIn(Decision.RECOMMEND, decisions)

    def test_data_quality_becomes_alert_not_equipment_recommendation(self):
        results = self.run_scenario("data_quality", 25)
        quality_results = [
            (incident, result)
            for _event, incident, result in results
            if incident.category.value == "DATA_QUALITY"
        ]
        self.assertTrue(quality_results)
        self.assertIn(
            Decision.DATA_QUALITY_ALERT,
            {result.decision for _incident, result in quality_results},
        )
        self.assertNotIn(
            Decision.RECOMMEND,
            {result.decision for _incident, result in quality_results},
        )


if __name__ == "__main__":
    unittest.main()
