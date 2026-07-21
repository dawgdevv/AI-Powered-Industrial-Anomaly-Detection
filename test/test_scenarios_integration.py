import unittest

from simulator.producer import FLEET, PlantSimulator, generate_mode_readings
from simulator.types import SimulatorConfig

from iot_stream.pipeline.detectors import DeviceDetectorSet
from iot_stream.schemas import SensorReading


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

    def test_faulty_mode_is_transient_and_only_affects_one_asset_at_a_time(self):
        simulator = PlantSimulator(
            SimulatorConfig(seed=42, mode="faulty", num_devices=6),
            timestamp_origin=1_700_000_000.0,
        )
        cycles = [simulator.read_cycle() for _ in range(320)]
        active_cycles = [cycle for cycle in cycles if any(r.fault_active for r in cycle)]
        self.assertTrue(active_cycles)
        self.assertTrue(
            all(sum(reading.fault_active for reading in cycle) == 1 for cycle in active_cycles)
        )
        first_fault_device = next(r.device_id for r in active_cycles[0] if r.fault_active)
        first_active_index = next(
            index
            for index, cycle in enumerate(cycles)
            if any(r.device_id == first_fault_device and r.fault_active for r in cycle)
        )
        self.assertTrue(
            any(
                not next(r for r in cycle if r.device_id == first_fault_device).fault_active
                for cycle in cycles[first_active_index + 90 :]
            )
        )

    def test_scheduler_only_selects_faults_compatible_with_asset(self):
        readings = generate_mode_readings("faulty", 7, 500)
        assets = {asset.device_id: asset for asset in FLEET}
        active = [reading for reading in readings if reading.fault_active]
        self.assertTrue(active)
        self.assertTrue(
            all(reading.fault_type in assets[reading.device_id].fault_types for reading in active)
        )


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
