# IoT Streaming Mock

A dependency-free TCP simulator for temperature, humidity, and vibration
telemetry from six named water-treatment assets. It emits newline-delimited
JSON over one broadcast TCP stream.

```bash
uv run main.py produce --mode normal --seed 42
uv run main.py consume --json
```

Faulty mode is a continuous demo workload. It begins with a 60-second clean
baseline, then one knowledge-aligned water-treatment equipment incident starts
every 60 seconds and runs for 40 seconds. Equipment scenarios are shuffled
without repeating until all six knowledge-base scenarios have run. To keep the
first retrieval demonstration clear, short data-quality conditions (duplicate
event, sequence gap, or intermittent reading) begin at 180 seconds; they then
start every 30 seconds and last 8 seconds. The agent receives only live
telemetry; `fault_type` is simulator-only ground truth and is not sent to the
pipeline:

```bash
uv run main.py produce --mode faulty --seed 42 --interval 0.1
```

Use `uv run` instead of activating the project virtual environment. It resolves
the Python version declared by the repository even when pyenv does not have
that version installed globally.

The default `normal` mode never injects faults. Fault metadata exists only for
simulator evaluation; the application pipeline uses observable telemetry and
transport behavior only.
