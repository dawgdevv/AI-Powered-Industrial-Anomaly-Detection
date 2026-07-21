import asyncio
import json

from simulator.producer import BroadcastServer, FLEET, PlantSimulator, plant_loop
from simulator.types import SensorReading, SimulatorConfig

TEST_DURATION = 25
TEST_INTERVAL = 0.02
HOST = "127.0.0.1"
PORT = 9999


async def consumer(received: list, host: str = HOST, port: int = PORT):
    reader, _writer = await asyncio.open_connection(host, port)
    try:
        async for line in reader:
            reading = SensorReading.from_dict(json.loads(line.decode()))
            received.append(reading)
    except asyncio.CancelledError:
        pass


async def main(duration: int = TEST_DURATION, host: str = HOST, port: int = PORT):
    server = BroadcastServer()
    simulator = PlantSimulator(
        SimulatorConfig(
            host=host,
            port=port,
            num_devices=len(FLEET),
            emit_interval=TEST_INTERVAL,
            seed=42,
            mode="faulty",
        ),
        timestamp_origin=1_700_000_000.0,
    )

    tcp_server = await asyncio.start_server(server.handle_client, host, port)
    actual_port = tcp_server.sockets[0].getsockname()[1]
    producer_task = asyncio.create_task(plant_loop(simulator, server, TEST_INTERVAL))

    received: list = []
    await asyncio.sleep(0.2)
    consumer_task = asyncio.create_task(consumer(received, host, actual_port))

    print(f"Running end-to-end test for {duration}s...\n")
    await asyncio.sleep(duration)

    consumer_task.cancel()
    producer_task.cancel()
    tcp_server.close()
    await tcp_server.wait_closed()

    print(f"\n--- Test result ---")
    print(f"Readings received over the socket: {len(received)}")
    devices = sorted(set(r.device_id for r in received))
    print(f"Devices seen: {devices}")

    nulls = sum(1 for r in received if r.vibration is None)
    faults_active = sum(1 for r in received if r.fault_active)
    duplicates = sum(1 for r in received if r.duplicate)
    print(f"Fault-active readings: {faults_active}")
    print(f"Null (MCAR dropout) readings: {nulls}")
    print(f"Duplicate readings: {duplicates}")
    for asset in FLEET:
        print(f"  {asset.device_id}: {asset.asset_id} · {asset.equipment_name}")
    print("PASS: producer and consumer talked over a real TCP socket." if received else "FAIL: no data received.")


if __name__ == "__main__":
    asyncio.run(main())
