import asyncio
import argparse
import json
import random
import time

from simulator.fault_models import RandomWalkChannel, ErrorDefinition, ANOMALY, MCAR, DUPLICATE_DATA, DRIFT, NO_ERROR
from simulator.types import SensorReading, SimulatorConfig

HOST = "0.0.0.0"
PORT = 9999
NUM_DEVICES = 4
EMIT_INTERVAL = 0.5

FAULT_ROTATION = [ANOMALY, DRIFT, MCAR, DUPLICATE_DATA]


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
    def __init__(self, device_id: str, fault_type: str):
        self.device_id = device_id
        self.fault_type = fault_type

        base_temp = random.uniform(20, 25)
        base_humidity = random.uniform(40, 60)
        base_vibration = random.uniform(0.1, 0.3)

        self.temperature = RandomWalkChannel(base_temp, variation_range=1.5, change_rate=0.3)
        self.humidity = RandomWalkChannel(base_humidity, variation_range=5.0, change_rate=0.8)
        self.vibration = RandomWalkChannel(
            base_vibration, variation_range=0.1, change_rate=0.02,
            error=_build_vibration_error(fault_type),
        )

    def read(self) -> SensorReading:
        temp = self.temperature.generate()
        humidity = self.humidity.generate()
        vibration = self.vibration.generate()

        return SensorReading(
            device_id=self.device_id,
            timestamp=round(time.time(), 3),
            temperature=temp["value"],
            humidity=humidity["value"],
            vibration=vibration["value"],
            fault_type=self.fault_type,
            fault_active=vibration["fault_active"],
            duplicate=vibration["duplicate"],
        )


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
        await asyncio.sleep(emit_interval + random.uniform(-0.05, 0.05))


async def run_producer(config: SimulatorConfig):
    server = BroadcastServer()
    sensors = [
        Sensor(f"sensor-{i+1}", fault_type=FAULT_ROTATION[i % len(FAULT_ROTATION)])
        for i in range(config.num_devices)
    ]

    tcp_server = await asyncio.start_server(server.handle_client, config.host, config.port)
    addr = tcp_server.sockets[0].getsockname()
    print(f"IoT producer broadcasting on {addr[0]}:{addr[1]}")
    print(f"Simulating {config.num_devices} devices, emitting every ~{config.emit_interval}s")
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
    args = parser.parse_args()

    config = SimulatorConfig(
        host=args.host,
        port=args.port,
        num_devices=args.num_devices,
        emit_interval=args.interval,
    )

    try:
        asyncio.run(run_producer(config))
    except KeyboardInterrupt:
        print("\nProducer stopped.")


if __name__ == "__main__":
    main()
