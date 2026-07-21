import asyncio
import argparse
import json
import random
import time
from typing import Optional

from simulator.fault_models import RandomWalkChannel, ErrorDefinition, ANOMALY, MCAR, DUPLICATE_DATA, DRIFT, NO_ERROR
from simulator.types import SensorReading, SimulatorConfig

HOST = "0.0.0.0"
PORT = 9999
NUM_DEVICES = 4
EMIT_INTERVAL = 0.5

FAULT_ROTATION = [ANOMALY, DRIFT, MCAR, DUPLICATE_DATA]
SCENARIOS = ("random", "known_fault", "novel_fault", "data_quality")
EQUIPMENT_TYPES = (
    "centrifugal_pump",
    "industrial_mixer",
    "ventilation_fan",
    "belt_conveyor",
)

KNOWN_DRIFT_END = 41
KNOWN_SPIKE_READING = 42
KNOWN_ELEVATED_END = 55
KNOWN_RECOVERY_END = 75
KNOWN_BASELINE = 0.30
KNOWN_MAX_ELEVATED = 0.80
KNOWN_SPIKE_SIZE = 2.50


def _build_vibration_error(fault_type: str) -> ErrorDefinition:
    if fault_type == ANOMALY:
        return ErrorDefinition(
            type=ANOMALY,
            probability_pos_anomaly=0.05,
            pos_anomaly_range=(2.0, 5.0),
        )
    if fault_type == DRIFT:
        return ErrorDefinition(
            type=DRIFT,
            drift_after_n_iterations=40,
            average_drift_rate=0.03,
            drift_variation_range=0.01,
        )
    if fault_type == MCAR:
        return ErrorDefinition(type=MCAR, mcar_probability=0.04)
    if fault_type == DUPLICATE_DATA:
        return ErrorDefinition(type=DUPLICATE_DATA, duplicate_probability=0.05)
    return ErrorDefinition(type=NO_ERROR)


class Sensor:
    def __init__(
        self,
        device_id: str,
        fault_type: str,
        *,
        equipment_type: str = "centrifugal_pump",
        scenario: str = "random",
        rng: Optional[random.Random] = None,
        timestamp_origin: Optional[float] = None,
        emit_interval: float = EMIT_INTERVAL,
    ):
        self.device_id = device_id
        self.fault_type = fault_type
        self.equipment_type = equipment_type
        self.scenario = scenario
        self.rng = rng or random.Random()
        self.timestamp_origin = timestamp_origin
        self.emit_interval = emit_interval
        self.sequence_number = 0
        self._last_event_id: Optional[str] = None

        base_temp = self.rng.uniform(20, 25)
        base_humidity = self.rng.uniform(40, 60)
        base_vibration = self.rng.uniform(0.1, 0.3)

        self.temperature = RandomWalkChannel(
            base_temp, variation_range=1.5, change_rate=0.3, rng=self.rng
        )
        self.humidity = RandomWalkChannel(
            base_humidity, variation_range=5.0, change_rate=0.8, rng=self.rng
        )
        self.vibration = RandomWalkChannel(
            base_vibration, variation_range=0.1, change_rate=0.02,
            error=_build_vibration_error(fault_type),
            rng=self.rng,
        )

    def read(self) -> SensorReading:
        self.sequence_number += 1
        if self.scenario == "data_quality" and self.sequence_number == 12:
            self.sequence_number += 1  # deterministic transport gap

        temp = self.temperature.generate()
        humidity = self.humidity.generate()
        vibration = (
            self._scenario_vibration()
            if self.scenario != "random"
            else self.vibration.generate()
        )

        event_id = f"{self.device_id}-evt-{self.sequence_number:06d}"
        duplicate = False
        if self.scenario == "data_quality" and self.sequence_number % 10 == 0:
            event_id = self._last_event_id or event_id
            duplicate = True

        timestamp = (
            round(self.timestamp_origin + self.sequence_number * self.emit_interval, 3)
            if self.timestamp_origin is not None
            else round(time.time(), 3)
        )

        reading = SensorReading(
            event_id=event_id,
            sequence_number=self.sequence_number,
            device_id=self.device_id,
            equipment_type=self.equipment_type,
            sensor_type="vibration",
            unit="mm/s",
            timestamp=timestamp,
            temperature=temp["value"],
            humidity=humidity["value"],
            vibration=vibration["value"],
            fault_type=self.scenario if self.scenario != "random" else self.fault_type,
            fault_active=vibration["fault_active"],
            duplicate=duplicate or vibration["duplicate"],
        )
        self._last_event_id = event_id
        return reading

    def _scenario_vibration(self) -> dict:
        """Return deterministic signal shapes without using fault labels downstream."""
        n = self.sequence_number
        if self.scenario == "known_fault":
            alternating_baseline = 0.16 if n % 2 else -0.16
            if n <= KNOWN_DRIFT_END:
                value = KNOWN_BASELINE + alternating_baseline + 0.012 * n
            elif n == KNOWN_SPIKE_READING:
                value = KNOWN_MAX_ELEVATED + KNOWN_SPIKE_SIZE
            elif n <= KNOWN_ELEVATED_END:
                value = KNOWN_MAX_ELEVATED + self.rng.uniform(-0.02, 0.02)
            elif n <= KNOWN_RECOVERY_END:
                progress = (n - KNOWN_ELEVATED_END) / (
                    KNOWN_RECOVERY_END - KNOWN_ELEVATED_END
                )
                value = KNOWN_MAX_ELEVATED - progress * (
                    KNOWN_MAX_ELEVATED - KNOWN_BASELINE
                )
            else:
                value = KNOWN_BASELINE + self.rng.uniform(-0.015, 0.015)
            return {
                "value": round(value, 3),
                "duplicate": False,
                "fault_active": 30 <= n <= KNOWN_RECOVERY_END,
            }
        if self.scenario == "novel_fault":
            value = 0.3 + self.rng.uniform(-0.015, 0.015)
            active = n == 20
            if active:
                value += 0.6
            return {"value": round(value, 3), "duplicate": False, "fault_active": active}
        value = KNOWN_BASELINE + self.rng.uniform(-0.015, 0.015)
        return {"value": round(value, 3), "duplicate": False, "fault_active": False}


def build_sensors(
    config: SimulatorConfig, *, timestamp_origin: Optional[float] = None
) -> list[Sensor]:
    seed = config.seed if config.seed is not None else random.randrange(2**32)
    return [
        Sensor(
            f"sensor-{i+1}",
            fault_type=FAULT_ROTATION[i % len(FAULT_ROTATION)],
            equipment_type=EQUIPMENT_TYPES[i % len(EQUIPMENT_TYPES)],
            scenario=(
                "normal"
                if config.scenario == "known_fault" and i > 0
                else config.scenario
            ),
            rng=random.Random(seed + i),
            timestamp_origin=timestamp_origin,
            emit_interval=config.emit_interval,
        )
        for i in range(config.num_devices)
    ]


def generate_scenario_readings(
    scenario: str, seed: int, count: int, *, timestamp_origin: float = 1_700_000_000.0
) -> list[SensorReading]:
    """Generate a repeatable single-device scenario for tests and demos."""
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown scenario: {scenario}")
    config = SimulatorConfig(
        num_devices=1, seed=seed, scenario=scenario, emit_interval=EMIT_INTERVAL
    )
    sensor = build_sensors(config, timestamp_origin=timestamp_origin)[0]
    return [sensor.read() for _ in range(count)]


class BroadcastServer:
    def __init__(self):
        self.clients: set[asyncio.StreamWriter] = set()

    async def handle_client(self, reader, writer: asyncio.StreamWriter):
        peer = writer.get_extra_info("peername")
        print(f"[+] Consumer connected: {peer}")
        self.clients.add(writer)
        try:
            while not reader.at_eof():
                await reader.read(1024)
        except (ConnectionResetError, asyncio.CancelledError):
            pass
        finally:
            print(f"[-] Consumer disconnected: {peer}")
            self.clients.discard(writer)
            writer.close()

    async def broadcast(self, reading: SensorReading):
        if not self.clients:
            return
        payload = (json.dumps(reading.to_dict()) + "\n").encode()
        dead = []
        for writer in self.clients:
            try:
                writer.write(payload)
                await writer.drain()
            except (ConnectionResetError, BrokenPipeError):
                dead.append(writer)
        for writer in dead:
            self.clients.discard(writer)


async def sensor_loop(sensor: Sensor, server: BroadcastServer, emit_interval: float = EMIT_INTERVAL):
    while True:
        reading = sensor.read()
        v_str = f"{reading.vibration:5.3f}" if reading.vibration is not None else " NULL"
        tag = f"{reading.fault_type:>9s}" if reading.fault_active else "  normal "
        dup = " (dup)" if reading.duplicate else ""
        print(
            f"[{reading.timestamp:.3f}] {reading.device_id:>10s} "
            f"T={reading.temperature:6.2f} H={reading.humidity:6.2f} "
            f"V={v_str}  {tag}{dup}"
        )
        await server.broadcast(reading)
        if reading.duplicate:
            await server.broadcast(reading)
        await asyncio.sleep(emit_interval + sensor.rng.uniform(-0.05, 0.05))


async def run_producer(config: SimulatorConfig):
    server = BroadcastServer()
    sensors = build_sensors(config, timestamp_origin=time.time())

    tcp_server = await asyncio.start_server(server.handle_client, config.host, config.port)
    addr = tcp_server.sockets[0].getsockname()
    print(f"IoT producer broadcasting on {addr[0]}:{addr[1]}")
    print(f"Simulating {config.num_devices} devices, emitting every ~{config.emit_interval}s")
    print(f"Scenario: {config.scenario}; seed: {config.seed if config.seed is not None else 'random'}")
    for s in sensors:
        print(f"  {s.device_id}: fault mode = {s.fault_type}")
    print("Waiting for consumers to connect (or run without one — data still flows)...\n")

    sensor_tasks = [asyncio.create_task(sensor_loop(s, server, config.emit_interval)) for s in sensors]

    async with tcp_server:
        await asyncio.gather(tcp_server.serve_forever(), *sensor_tasks)


def main():
    parser = argparse.ArgumentParser(description="IoT Sensor Simulator — Producer")
    parser.add_argument("--host", default=HOST, help=f"Bind host (default: {HOST})")
    parser.add_argument("--port", type=int, default=PORT, help=f"Bind port (default: {PORT})")
    parser.add_argument("--num-devices", type=int, default=NUM_DEVICES, help=f"Number of simulated sensors (default: {NUM_DEVICES})")
    parser.add_argument("--interval", type=float, default=EMIT_INTERVAL, help=f"Seconds between readings per device (default: {EMIT_INTERVAL})")
    parser.add_argument("--seed", type=int, help="Deterministic random seed")
    parser.add_argument("--scenario", choices=SCENARIOS, default="random", help="Named demo scenario")
    args = parser.parse_args()

    config = SimulatorConfig(
        host=args.host,
        port=args.port,
        num_devices=args.num_devices,
        emit_interval=args.interval,
        seed=args.seed,
        scenario=args.scenario,
    )

    try:
        asyncio.run(run_producer(config))
    except KeyboardInterrupt:
        print("\nProducer stopped.")


if __name__ == "__main__":
    main()
