import json
import unittest
from pathlib import Path

from simulator.producer import FLEET, PlantSimulator, fault_for_asset, generate_mode_readings
from simulator.types import SimulatorConfig

from iot_stream.pipeline.detectors import DeviceDetectorSet
from iot_stream.schemas import SensorReading


CORPUS_PATH = Path(__file__).parents[1] / "src/iot_stream/knowledge/incidents.json"


class FleetAndModeTests(unittest.TestCase):
    def test_water_treatment_fleet_has_six_unique_named_assets(self):
        self.assertEqual(len(FLEET), 6)
        self.assertEqual(len({asset.device_id for asset in FLEET}), 6)
        self.assertEqual(len({asset.asset_id for asset in FLEET}), 6)
        self.assertTrue(all(asset.equipment_name and asset.area for asset in FLEET))

    def test_same_seed_and_mode_are_identical(self):
        first = generate_mode_readings("faulty", 42, 180)
        second = generate_mode_readings("faulty", 42, 180)
        self.assertEqual(first, second)

    def test_normal_mode_keeps_all_six_assets_healthy(self):
        readings = generate_mode_readings("normal", 42, 180)
        self.assertEqual({item.device_id for item in readings}, {a.device_id for a in FLEET})
        self.assertTrue(all(not item.fault_active for item in readings))
        self.assertTrue(all(item.fault_type is None for item in readings))

    def test_faulty_mode_runs_one_equipment_and_one_data_quality_condition_at_most(self):
        simulator = PlantSimulator(
            SimulatorConfig(seed=42, mode="faulty", num_devices=6),
            timestamp_origin=1_700_000_000.0,
        )
        equipment_starts = []
        quality_starts = []
        for _ in range(360):
            simulator.read_cycle()
            equipment = simulator.scheduler.active_equipment
            quality = simulator.scheduler.active_quality
            self.assertIn(equipment.kind if equipment else None, {None, "equipment"})
            self.assertIn(quality.kind if quality else None, {None, "data_quality"})
            if equipment and equipment.start_tick == simulator.scheduler.tick:
                equipment_starts.append(equipment.device_id)
            if quality and quality.start_tick == simulator.scheduler.tick:
                quality_starts.append(quality.fault_type)

        self.assertGreaterEqual(len(equipment_starts), 3)
        self.assertGreaterEqual(len(quality_starts), 5)
        self.assertEqual(len(equipment_starts), len(set(equipment_starts)))

    def test_each_knowledge_scenario_appears_before_the_equipment_deck_repeats(self):
        simulator = PlantSimulator(SimulatorConfig(seed=42, mode="faulty", num_devices=6))
        equipment_starts = []
        for _ in range(750):
            simulator.read_cycle()
            equipment = simulator.scheduler.active_equipment
            if equipment and equipment.start_tick == simulator.scheduler.tick:
                equipment_starts.append(equipment.device_id)

        self.assertEqual(set(equipment_starts[: len(FLEET)]), {asset.device_id for asset in FLEET})

    def test_scheduler_only_selects_faults_compatible_with_asset(self):
        readings = generate_mode_readings("faulty", 7, 500)
        assets = {asset.device_id: asset for asset in FLEET}
        active = [reading for reading in readings if reading.fault_active]
        self.assertTrue(active)
        self.assertTrue(
            all(reading.fault_type in assets[reading.device_id].fault_types for reading in active)
        )

    def test_every_demo_fault_has_an_exact_water_treatment_scenario(self):
        """Keep the random video demo aligned with its visible knowledge-base match."""
        scenarios = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
        scenarios_by_id = {scenario["incident_id"]: scenario for scenario in scenarios}
        self.assertEqual({asset.knowledge_incident_id for asset in FLEET}, set(scenarios_by_id))
        self.assertTrue(all(
            scenarios_by_id[asset.knowledge_incident_id]["equipment_type"] == asset.equipment_type
            and scenarios_by_id[asset.knowledge_incident_id]["fault_family"] == fault_for_asset(asset)
            for asset in FLEET
        ))


class DetectionBoundaryTests(unittest.TestCase):
    def test_faulty_telemetry_creates_detector_events(self):
        detector_sets = {asset.device_id: DeviceDetectorSet() for asset in FLEET}
        events = []
        for simulated in generate_mode_readings("faulty", 42, 320):
            reading = SensorReading.from_dict(simulated.to_dict())
            events.extend(detector_sets[reading.device_id].check(reading))
        self.assertTrue(events)
        self.assertTrue(
            {event.detector for event in events}
            & {"spike", "drift", "dropout", "duplicate_event", "sequence_gap"}
        )

    def test_ground_truth_label_alone_does_not_create_an_incident(self):
        detector = DeviceDetectorSet()
        events = []
        readings = generate_mode_readings("normal", 42, 80, num_devices=1)
        for simulated in readings:
            payload = simulated.to_dict()
            payload.update(fault_type="fabricated_label", fault_active=True)
            events.extend(detector.check(SensorReading.from_dict(payload)))
        self.assertEqual(events, [])


if __name__ == "__main__":
    unittest.main()
