import unittest

from simulator.producer import (
    DATA_QUALITY_FAULT_INTERVAL_SECONDS,
    EQUIPMENT_FAULT_DURATION_SECONDS,
    EQUIPMENT_FAULT_INTERVAL_SECONDS,
    WARMUP_SECONDS,
    PlantSimulator,
)
from simulator.types import SimulatorConfig


class FaultyModeTests(unittest.TestCase):
    def test_faulty_workload_starts_on_a_repeatable_mixed_fault_cadence(self):
        interval = 0.5
        simulator = PlantSimulator(SimulatorConfig(mode="faulty", seed=42, emit_interval=interval))
        warmup_ticks = int(WARMUP_SECONDS / interval)
        equipment_duration_ticks = int(EQUIPMENT_FAULT_DURATION_SECONDS / interval)
        equipment_interval_ticks = int(EQUIPMENT_FAULT_INTERVAL_SECONDS / interval)
        quality_interval_ticks = int(DATA_QUALITY_FAULT_INTERVAL_SECONDS / interval)

        before = [reading for _ in range(warmup_ticks - 1) for reading in simulator.read_cycle()]
        self.assertFalse(any(reading.fault_active for reading in before))

        simulator.read_cycle()
        first_equipment = simulator.scheduler.active_equipment
        self.assertIsNotNone(first_equipment)
        self.assertEqual(first_equipment.kind, "equipment")
        self.assertEqual(first_equipment.start_tick, warmup_ticks)
        self.assertEqual(first_equipment.duration, equipment_duration_ticks)

        for _ in range(quality_interval_ticks):
            simulator.read_cycle()
        quality_fault = simulator.scheduler.active_quality
        self.assertIsNotNone(quality_fault)
        self.assertEqual(quality_fault.kind, "data_quality")
        self.assertEqual(quality_fault.start_tick, warmup_ticks + quality_interval_ticks)

        while simulator.scheduler.tick < warmup_ticks + equipment_interval_ticks:
            simulator.read_cycle()
        second_equipment = simulator.scheduler.active_equipment
        self.assertIsNotNone(second_equipment)
        self.assertEqual(second_equipment.start_tick, warmup_ticks + equipment_interval_ticks)
        self.assertNotEqual(second_equipment.device_id, first_equipment.device_id)

    def test_single_asset_fleet_only_uses_compatible_quality_anomalies(self):
        simulator = PlantSimulator(SimulatorConfig(mode="faulty", seed=42, num_devices=1, emit_interval=0.5))
        quality_types = []
        for _ in range(250):
            simulator.read_cycle()
            quality_fault = simulator.scheduler.active_quality
            if quality_fault and quality_fault.start_tick == simulator.scheduler.tick:
                quality_types.append(quality_fault.fault_type)
        self.assertTrue(quality_types)
        self.assertEqual(set(quality_types), {"duplicate_event"})


if __name__ == "__main__":
    unittest.main()
