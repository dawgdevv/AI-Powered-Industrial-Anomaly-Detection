import argparse
import asyncio
import json
import random
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from simulator.fault_models import RandomWalkChannel
from simulator.types import SensorReading, SimulatorConfig

HOST = "0.0.0.0"
PORT = 9999
NUM_DEVICES = 6
EMIT_INTERVAL = 0.5
MODES = ("normal", "faulty")

# Continuous operational-demo workload: each equipment scenario is taken from
# the same catalog Chroma indexes; data-quality conditions exercise the rest of
# the pipeline without giving the agent a mock fault label.
WARMUP_SECONDS = 60.0
EQUIPMENT_FAULT_DURATION_SECONDS = 40.0
EQUIPMENT_FAULT_INTERVAL_SECONDS = 60.0
DATA_QUALITY_FAULT_DURATION_SECONDS = 8.0
DATA_QUALITY_FAULT_INTERVAL_SECONDS = 30.0
DATA_QUALITY_FIRST_FAULT_SECONDS = 180.0
DATA_QUALITY_FAULT_TYPES = ("duplicate_event", "sequence_gap", "intermittent_operation")


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
    knowledge_incident_id: str


FLEET: tuple[Asset, ...] = (
    Asset(
        "sensor-1", "P-101", "Raw Water Intake Pump", "centrifugal_pump",
        "Intake Station", 24.0, 62.0, 0.30,
        ("cavitation", "bearing_degradation", "bearing_misalignment", "duplicate_event"), "WT-INC-001",
    ),
    Asset(
        "sensor-2", "B-201", "Aeration Blower", "aeration_blower",
        "Biological Treatment", 31.0, 55.0, 0.42,
        ("blower_overheating", "bearing_degradation", "compressor_bearing_damage", "sequence_gap"), "WT-INC-002",
    ),
    Asset(
        "sensor-3", "M-301", "Flash Mixer", "flash_mixer",
        "Coagulation Basin", 26.0, 68.0, 0.34,
        ("shaft_imbalance", "bearing_local_defect", "intermittent_operation", "duplicate_event"), "WT-INC-003",
    ),
    Asset(
        "sensor-4", "C-401", "Sludge Dewatering Centrifuge", "decanter_centrifuge",
        "Solids Handling", 35.0, 72.0, 0.58,
        ("rotor_imbalance", "bearing_degradation", "vibration_bearing_seal_failure", "sequence_gap"), "WT-INC-004",
    ),
    Asset(
        "sensor-5", "P-501", "Chemical Dosing Pump", "metering_pump",
        "Chemical Room", 23.0, 48.0, 0.20,
        ("intermittent_operation", "cavitation", "coupling_failure", "duplicate_event"), "WT-INC-005",
    ),
    Asset(
        "sensor-6", "SC-601", "Sludge Screw Conveyor", "screw_conveyor",
        "Dewatering Area", 29.0, 66.0, 0.46,
        ("mechanical_overload", "bearing_degradation", "compressor_bearing_damage", "sequence_gap"), "WT-INC-006",
    ),
)

KNOWLEDGE_CORPUS_PATH = Path(__file__).resolve().parents[2] / "src/iot_stream/knowledge/incidents.json"


def _load_demo_scenarios() -> dict[str, dict[str, object]]:
    """The faulty-mode source of truth is the same catalog that Chroma indexes."""
    records = json.loads(KNOWLEDGE_CORPUS_PATH.read_text(encoding="utf-8"))
    return {str(record["incident_id"]): record for record in records}


DEMO_SCENARIOS = _load_demo_scenarios()


def fault_for_asset(asset: Asset) -> str:
    """Resolve the live mock's waveform from its water-treatment scenario."""
    scenario = DEMO_SCENARIOS.get(asset.knowledge_incident_id)
    if scenario is None:
        raise ValueError(f"Missing knowledge scenario {asset.knowledge_incident_id}")
    if scenario.get("equipment_type") != asset.equipment_type:
        raise ValueError(f"Scenario {asset.knowledge_incident_id} does not match {asset.device_id}")
    return str(scenario["fault_family"])


@dataclass(frozen=True)
class ActiveFault:
    device_id: str
    fault_type: str
    kind: str
    start_tick: int
    duration: int
    severity: float

    def progress(self, tick: int) -> float:
        return max(0.0, min(1.0, (tick - self.start_tick) / max(self.duration - 1, 1)))


class FaultScheduler:
    """Seeded mixed-fault scheduler for an ongoing, realistic operations demo."""

    def __init__(self, assets: list[Asset], rng: random.Random, mode: str, emit_interval: float):
        if mode not in MODES:
            raise ValueError(f"Unknown mode: {mode}")
        self.assets = assets
        self.rng = rng
        self.mode = mode
        self.tick = 0
        self.active_equipment: ActiveFault | None = None
        self.active_quality: ActiveFault | None = None
        self.warmup_ticks = max(1, math.ceil(WARMUP_SECONDS / max(emit_interval, 0.001)))
        self.equipment_duration_ticks = max(2, math.ceil(EQUIPMENT_FAULT_DURATION_SECONDS / max(emit_interval, 0.001)))
        self.equipment_interval_ticks = max(2, math.ceil(EQUIPMENT_FAULT_INTERVAL_SECONDS / max(emit_interval, 0.001)))
        self.quality_duration_ticks = max(2, math.ceil(DATA_QUALITY_FAULT_DURATION_SECONDS / max(emit_interval, 0.001)))
        self.quality_interval_ticks = max(2, math.ceil(DATA_QUALITY_FAULT_INTERVAL_SECONDS / max(emit_interval, 0.001)))
        self.next_equipment_tick = self.warmup_ticks if mode == "faulty" else None
        self.next_quality_tick = max(1, math.ceil(DATA_QUALITY_FIRST_FAULT_SECONDS / max(emit_interval, 0.001))) if mode == "faulty" else None
        self._equipment_deck: list[Asset] = []
        self._quality_type_deck: list[str] = []

    def _next_equipment_asset(self) -> Asset:
        if not self._equipment_deck:
            self._equipment_deck = list(self.assets)
            self.rng.shuffle(self._equipment_deck)
        return self._equipment_deck.pop()

    def _next_quality_fault(self) -> tuple[Asset, str]:
        if not self._quality_type_deck:
            self._quality_type_deck = [
                fault_type
                for fault_type in DATA_QUALITY_FAULT_TYPES
                if any(fault_type in asset.fault_types for asset in self.assets)
            ]
            self.rng.shuffle(self._quality_type_deck)
        fault_type = self._quality_type_deck.pop()
        candidates = [asset for asset in self.assets if fault_type in asset.fault_types]
        return self.rng.choice(candidates), fault_type

    @staticmethod
    def _finished(fault: ActiveFault | None, tick: int) -> bool:
        return fault is not None and tick >= fault.start_tick + fault.duration

    def advance(self) -> tuple[ActiveFault, ...]:
        self.tick += 1
        if self.mode == "normal":
            return ()

        if self._finished(self.active_equipment, self.tick):
            self.active_equipment = None
        if self._finished(self.active_quality, self.tick):
            self.active_quality = None

        if self.active_equipment is None and self.tick >= (self.next_equipment_tick or 0):
            asset = self._next_equipment_asset()
            self.active_equipment = ActiveFault(
                device_id=asset.device_id,
                fault_type=fault_for_asset(asset),
                kind="equipment",
                start_tick=self.tick,
                duration=self.equipment_duration_ticks,
                severity=self.rng.uniform(0.85, 1.15),
            )
            self.next_equipment_tick = self.tick + self.equipment_interval_ticks

        if self.active_quality is None and self.tick >= (self.next_quality_tick or 0):
            asset, fault_type = self._next_quality_fault()
            self.active_quality = ActiveFault(
                device_id=asset.device_id,
                fault_type=fault_type,
                kind="data_quality",
                start_tick=self.tick,
                duration=self.quality_duration_ticks,
                severity=1.0,
            )
            self.next_quality_tick = self.tick + self.quality_interval_ticks
        return tuple(fault for fault in (self.active_equipment, self.active_quality) if fault is not None)


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

    def read(self, faults: tuple[ActiveFault, ...] = (), *, tick: int = 0) -> SensorReading:
        self.sequence_number += 1
        temperature = self.temperature.generate()["value"]
        humidity = self.humidity.generate()["value"]
        vibration = self.vibration.generate()["value"]
        duplicate = False
        fault_type = None

        active_faults = [fault for fault in faults if fault.device_id == self.device_id]
        active = bool(active_faults)
        if active:
            primary = next((fault for fault in active_faults if fault.kind == "equipment"), active_faults[0])
            fault_type = primary.fault_type
        for fault in active_faults:
            temperature, vibration, fault_duplicate = self._apply_fault(
                fault, tick, temperature, vibration
            )
            duplicate = duplicate or fault_duplicate
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
        # A sine envelope remains gradual over the 40-second scenario but rises
        # fast enough for the fixed per-reading detector thresholds at the
        # dashboard's 0.1-second demo cadence. A linear ramp was absorbed into
        # the rolling baseline before it could produce an incident.
        envelope = math.sin(math.pi * progress)
        severity = fault.severity
        duplicate = False

        if fault.fault_type in {"cavitation", "coupling_failure"}:
            vibration += 1.15 * envelope * severity
        elif fault.fault_type in {"bearing_degradation", "bearing_misalignment", "bearing_local_defect", "vibration_bearing_seal_failure"}:
            vibration += 1.25 * envelope * severity
            temperature += 7.0 * envelope * severity
        elif fault.fault_type in {"blower_overheating", "compressor_bearing_damage"}:
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
            self.assets, random.Random(seed + 10_000), config.mode, config.emit_interval
        )

    def read_cycle(self) -> list[SensorReading]:
        faults = self.scheduler.advance()
        return [sensor.read(faults, tick=self.scheduler.tick) for sensor in self.sensors]


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
    if config.mode == "faulty":
        print(f"Faulty workload: {WARMUP_SECONDS:.0f}s clean baseline; one knowledge-backed equipment scenario runs every {EQUIPMENT_FAULT_INTERVAL_SECONDS:.0f}s for {EQUIPMENT_FAULT_DURATION_SECONDS:.0f}s; data-quality anomalies begin at {DATA_QUALITY_FIRST_FAULT_SECONDS:.0f}s and then run every {DATA_QUALITY_FAULT_INTERVAL_SECONDS:.0f}s for {DATA_QUALITY_FAULT_DURATION_SECONDS:.0f}s.")
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
