import argparse
import asyncio
import json
import random
import time
from dataclasses import dataclass
from typing import Optional

from simulator.fault_models import RandomWalkChannel
from simulator.types import SensorReading, SimulatorConfig

HOST = "0.0.0.0"
PORT = 9999
NUM_DEVICES = 6
EMIT_INTERVAL = 0.5
MODES = ("normal", "faulty")

WARMUP_RANGE = (60, 100)
HEALTHY_GAP_RANGE = (40, 100)
FAULT_DURATION_RANGE = (30, 90)


@dataclass(frozen=True)
class Asset:
    device_id: str
    asset_id: str
    equipment_name: str
    equipment_type: str
    area: str
    base_temperature: float
    base_humidity: float
    base_vibration: float
    fault_types: tuple[str, ...]


FLEET: tuple[Asset, ...] = (
    Asset(
        "sensor-1", "P-101", "Raw Water Intake Pump", "centrifugal_pump",
        "Intake Station", 24.0, 62.0, 0.30,
        ("cavitation", "bearing_degradation", "duplicate_event"),
    ),
    Asset(
        "sensor-2", "B-201", "Aeration Blower", "aeration_blower",
        "Biological Treatment", 31.0, 55.0, 0.42,
        ("blower_overheating", "bearing_degradation", "sequence_gap"),
    ),
    Asset(
        "sensor-3", "M-301", "Flash Mixer", "flash_mixer",
        "Coagulation Basin", 26.0, 68.0, 0.34,
        ("shaft_imbalance", "intermittent_operation", "duplicate_event"),
    ),
    Asset(
        "sensor-4", "C-401", "Sludge Dewatering Centrifuge", "decanter_centrifuge",
        "Solids Handling", 35.0, 72.0, 0.58,
        ("rotor_imbalance", "bearing_degradation", "sequence_gap"),
    ),
    Asset(
        "sensor-5", "P-501", "Chemical Dosing Pump", "metering_pump",
        "Chemical Room", 23.0, 48.0, 0.20,
        ("intermittent_operation", "cavitation", "duplicate_event"),
    ),
    Asset(
        "sensor-6", "SC-601", "Sludge Screw Conveyor", "screw_conveyor",
        "Dewatering Area", 29.0, 66.0, 0.46,
        ("mechanical_overload", "bearing_degradation", "sequence_gap"),
    ),
)


@dataclass(frozen=True)
class ActiveFault:
    device_id: str
    fault_type: str
    start_tick: int
    duration: int
    severity: float

    def progress(self, tick: int) -> float:
        return max(0.0, min(1.0, (tick - self.start_tick) / max(self.duration - 1, 1)))


class FaultScheduler:
    """Seeded single-fault scheduler shared by the whole simulated plant."""

    def __init__(self, assets: list[Asset], rng: random.Random, mode: str):
        if mode not in MODES:
            raise ValueError(f"Unknown mode: {mode}")
        self.assets = assets
        self.rng = rng
        self.mode = mode
        self.tick = 0
        self.active_fault: ActiveFault | None = None
        self.next_fault_tick = (
            self.rng.randint(*WARMUP_RANGE) if mode == "faulty" else None
        )

    def advance(self) -> ActiveFault | None:
        self.tick += 1
        if self.mode == "normal":
            return None

        if self.active_fault is not None:
            end_tick = self.active_fault.start_tick + self.active_fault.duration
            if self.tick >= end_tick:
                self.active_fault = None
                self.next_fault_tick = self.tick + self.rng.randint(*HEALTHY_GAP_RANGE)

        if self.active_fault is None and self.tick >= (self.next_fault_tick or 0):
            asset = self.rng.choice(self.assets)
            self.active_fault = ActiveFault(
                device_id=asset.device_id,
                fault_type=self.rng.choice(asset.fault_types),
                start_tick=self.tick,
                duration=self.rng.randint(*FAULT_DURATION_RANGE),
                severity=self.rng.uniform(0.85, 1.15),
            )
        return self.active_fault


class Sensor:
    def __init__(
        self,
        asset: Asset,
        *,
        rng: Optional[random.Random] = None,
        timestamp_origin: Optional[float] = None,
        emit_interval: float = EMIT_INTERVAL,
    ):
        self.asset = asset
        self.device_id = asset.device_id
        self.rng = rng or random.Random()
        self.timestamp_origin = timestamp_origin
        self.emit_interval = emit_interval
        self.sequence_number = 0

        self.temperature = RandomWalkChannel(
            asset.base_temperature, variation_range=1.2, change_rate=0.15, rng=self.rng
        )
        self.humidity = RandomWalkChannel(
            asset.base_humidity, variation_range=3.0, change_rate=0.35, rng=self.rng
        )
        self.vibration = RandomWalkChannel(
            asset.base_vibration, variation_range=0.08, change_rate=0.012, rng=self.rng
        )

    def read(self, fault: ActiveFault | None = None, *, tick: int = 0) -> SensorReading:
        self.sequence_number += 1
        temperature = self.temperature.generate()["value"]
        humidity = self.humidity.generate()["value"]
        vibration = self.vibration.generate()["value"]
        duplicate = False
        fault_type = None

        active = fault is not None and fault.device_id == self.device_id
        if active:
            fault_type = fault.fault_type
            temperature, vibration, duplicate = self._apply_fault(
                fault, tick, temperature, vibration
            )
            if fault.fault_type == "sequence_gap" and tick % 8 == 0:
                self.sequence_number += 1

        event_id = f"{self.device_id}-evt-{self.sequence_number:06d}"
        timestamp = (
            round(self.timestamp_origin + self.sequence_number * self.emit_interval, 3)
            if self.timestamp_origin is not None
            else round(time.time(), 3)
        )
        return SensorReading(
            event_id=event_id,
            sequence_number=self.sequence_number,
            device_id=self.device_id,
            asset_id=self.asset.asset_id,
            equipment_name=self.asset.equipment_name,
            equipment_type=self.asset.equipment_type,
            area=self.asset.area,
            sensor_type="vibration",
            unit="mm/s",
            timestamp=timestamp,
            temperature=temperature,
            humidity=humidity,
            vibration=vibration,
            fault_type=fault_type,
            fault_active=active,
            duplicate=duplicate,
        )

    def _apply_fault(
        self,
        fault: ActiveFault,
        tick: int,
        temperature: float,
        vibration: float,
    ) -> tuple[float, float | None, bool]:
        progress = fault.progress(tick)
        envelope = 1.0 - abs(2.0 * progress - 1.0)
        severity = fault.severity
        duplicate = False

        if fault.fault_type == "cavitation":
            vibration += (1.0 + self.rng.uniform(0.2, 0.9)) * severity if tick % 5 == 0 else 0.15 * envelope
        elif fault.fault_type == "bearing_degradation":
            vibration += 1.25 * envelope * severity
            temperature += 7.0 * envelope * severity
        elif fault.fault_type == "blower_overheating":
            temperature += 11.0 * envelope * severity
            vibration += 0.9 * envelope * severity
        elif fault.fault_type == "shaft_imbalance":
            vibration += (0.75 + 0.18 * (tick % 2)) * envelope * severity
        elif fault.fault_type == "rotor_imbalance":
            vibration += (1.4 + 0.25 * (tick % 3)) * envelope * severity
            temperature += 5.0 * envelope * severity
        elif fault.fault_type == "intermittent_operation":
            vibration = None if tick % 3 != 0 else vibration * 0.15
        elif fault.fault_type == "mechanical_overload":
            vibration += 1.1 * envelope * severity
            temperature += 9.0 * envelope * severity
        elif fault.fault_type == "duplicate_event":
            duplicate = tick % 6 == 0

        rounded_temperature = round(temperature, 3)
        rounded_vibration = round(vibration, 3) if vibration is not None else None
        return rounded_temperature, rounded_vibration, duplicate


class PlantSimulator:
    def __init__(
        self, config: SimulatorConfig, *, timestamp_origin: Optional[float] = None
    ):
        if config.mode not in MODES:
            raise ValueError(f"Unknown mode: {config.mode}")
        if not 1 <= config.num_devices <= len(FLEET):
            raise ValueError(f"num_devices must be between 1 and {len(FLEET)}")
        seed = config.seed if config.seed is not None else random.randrange(2**32)
        self.seed = seed
        self.assets = list(FLEET[: config.num_devices])
        self.sensors = [
            Sensor(
                asset,
                rng=random.Random(seed + index + 1),
                timestamp_origin=timestamp_origin,
                emit_interval=config.emit_interval,
            )
            for index, asset in enumerate(self.assets)
        ]
        self.scheduler = FaultScheduler(
            self.assets, random.Random(seed + 10_000), config.mode
        )

    def read_cycle(self) -> list[SensorReading]:
        fault = self.scheduler.advance()
        return [sensor.read(fault, tick=self.scheduler.tick) for sensor in self.sensors]


def build_sensors(
    config: SimulatorConfig, *, timestamp_origin: Optional[float] = None
) -> list[Sensor]:
    """Build the configured leading subset of the explicit plant fleet."""
    return PlantSimulator(config, timestamp_origin=timestamp_origin).sensors


def generate_mode_readings(
    mode: str,
    seed: int,
    cycles: int,
    *,
    num_devices: int = NUM_DEVICES,
    timestamp_origin: float = 1_700_000_000.0,
) -> list[SensorReading]:
    """Generate deterministic plant cycles for tests and demos."""
    simulator = PlantSimulator(
        SimulatorConfig(
            num_devices=num_devices,
            seed=seed,
            mode=mode,
            emit_interval=EMIT_INTERVAL,
        ),
        timestamp_origin=timestamp_origin,
    )
    return [reading for _ in range(cycles) for reading in simulator.read_cycle()]


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


async def plant_loop(
    simulator: PlantSimulator,
    server: BroadcastServer,
    emit_interval: float = EMIT_INTERVAL,
):
    while True:
        for reading in simulator.read_cycle():
            vibration = f"{reading.vibration:5.3f}" if reading.vibration is not None else " NULL"
            state = f"FAULT {reading.fault_type}" if reading.fault_active else "normal"
            print(
                f"[{reading.timestamp:.3f}] {reading.asset_id:>6s} "
                f"T={reading.temperature:6.2f} H={reading.humidity:6.2f} "
                f"V={vibration}  {state}"
            )
            await server.broadcast(reading)
            if reading.duplicate:
                await server.broadcast(reading)
        await asyncio.sleep(max(0.0, emit_interval))


async def run_producer(config: SimulatorConfig):
    server = BroadcastServer()
    simulator = PlantSimulator(config, timestamp_origin=time.time())
    tcp_server = await asyncio.start_server(server.handle_client, config.host, config.port)
    addr = tcp_server.sockets[0].getsockname()
    print(f"IoT producer broadcasting on {addr[0]}:{addr[1]}")
    print(f"Water treatment fleet: {config.num_devices}/{len(FLEET)} assets")
    print(f"Mode: {config.mode}; interval: {config.emit_interval}s; seed: {simulator.seed}")
    for asset in simulator.assets:
        print(f"  {asset.device_id}: {asset.asset_id} · {asset.equipment_name} · {asset.area}")
    print("Waiting for consumers to connect (or run without one — data still flows)...\n")

    async with tcp_server:
        await asyncio.gather(
            tcp_server.serve_forever(),
            plant_loop(simulator, server, config.emit_interval),
        )


def main():
    parser = argparse.ArgumentParser(description="Water Treatment IoT Simulator — Producer")
    parser.add_argument("--host", default=HOST, help=f"Bind host (default: {HOST})")
    parser.add_argument("--port", type=int, default=PORT, help=f"Bind port (default: {PORT})")
    parser.add_argument(
        "--num-devices", type=int, choices=range(1, len(FLEET) + 1),
        default=NUM_DEVICES, help=f"Leading fleet assets to simulate (default: {NUM_DEVICES})",
    )
    parser.add_argument(
        "--interval", type=float, default=EMIT_INTERVAL,
        help=f"Seconds between plant cycles (default: {EMIT_INTERVAL})",
    )
    parser.add_argument("--seed", type=int, help="Deterministic random seed")
    parser.add_argument("--mode", choices=MODES, default="normal", help="Plant operating mode")
    parser.add_argument("--scenario", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.scenario is not None:
        parser.error("--scenario was removed; use --mode normal or --mode faulty")
    if args.interval < 0:
        parser.error("--interval must be zero or greater")

    config = SimulatorConfig(
        host=args.host,
        port=args.port,
        num_devices=args.num_devices,
        emit_interval=args.interval,
        seed=args.seed,
        mode=args.mode,
    )
    try:
        asyncio.run(run_producer(config))
    except KeyboardInterrupt:
        print("\nProducer stopped.")


if __name__ == "__main__":
    main()
