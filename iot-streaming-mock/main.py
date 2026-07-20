import sys
import argparse

from simulator.producer import main as producer_main
from simulator.consumer import main as consumer_main
from simulator.test_e2e import main as e2e_main


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("IoT Streaming Agentic RAG — Simulator")
        print()
        print("Usage: python main.py <command> [options]")
        print()
        print("Commands:")
        print("  produce   Run the IoT sensor simulator (broadcasts over TCP)")
        print("  consume   Connect to a running producer and view live readings")
        print("  e2e       Run an end-to-end integration test")
        print()
        print("For command-specific help:")
        print("  python main.py produce --help")
        print("  python main.py consume --help")
        return

    command = sys.argv[1]
    sys.argv = [sys.argv[0]] + sys.argv[2:]

    if command == "produce":
        producer_main()
    elif command == "consume":
        consumer_main()
    elif command == "e2e":
        e2e_main()
    else:
        print(f"Unknown command: {command}")
        print("Available: produce, consume, e2e")
        sys.exit(1)


if __name__ == "__main__":
    main()
