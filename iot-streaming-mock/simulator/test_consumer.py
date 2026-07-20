import asyncio
import sys

from simulator.consumer import run_consumer

HOST = "localhost"
PORT = 9999


async def main():
    await run_consumer(HOST, PORT)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nConsumer stopped.")
    except ConnectionRefusedError:
        print("Could not connect. Is the producer running?")
        sys.exit(1)
