import asyncio
import argparse
import json
import sys

from simulator.types import SensorReading


async def run_consumer(host: str, port: int, json_output: bool = False):
    reader, _writer = await asyncio.open_connection(host, port)
    if not json_output:
        print(f"Connected to producer at {host}:{port}. Listening for live readings...\n")

    count = 0
    async for line in reader:
        reading = SensorReading.from_dict(json.loads(line.decode()))
        count += 1

        if json_output:
            print(json.dumps(reading.to_dict()))
            sys.stdout.flush()
            continue

        flag = "\U0001f534" if reading.fault_active else "  "
        v = reading.vibration
        v_str = f"{v:5.3f}" if v is not None else " NULL"
        dup = " (dup)" if reading.duplicate else ""
        print(
            f"{flag} #{count:04d} {reading.device_id:>10s} | "
            f"T={reading.temperature:6.2f} H={reading.humidity:6.2f} "
            f"V={v_str}  fault={reading.fault_type}{dup}"
        )


def main():
    parser = argparse.ArgumentParser(description="IoT Sensor Simulator — Consumer")
    parser.add_argument("--host", default="localhost", help="Producer host (default: localhost)")
    parser.add_argument("--port", type=int, default=9999, help="Producer port (default: 9999)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON lines instead of formatted table")
    args = parser.parse_args()

    try:
        asyncio.run(run_consumer(args.host, args.port, args.json))
    except KeyboardInterrupt:
        print("\nConsumer stopped.")
    except ConnectionRefusedError:
        print("Could not connect. Is the producer running?")
        sys.exit(1)


if __name__ == "__main__":
    main()
