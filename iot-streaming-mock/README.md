# IoT Streaming Mock

A dependency-free TCP simulator for temperature, humidity, and vibration
telemetry from six named water-treatment assets. It emits newline-delimited
JSON over one broadcast TCP stream.

```bash
uv run main.py produce --mode normal --seed 42
uv run main.py consume --json
```

Faulty mode schedules compatible faults on random assets, then recovers them
automatically. A seed makes the complete run repeatable:

```bash
uv run main.py produce --mode faulty --seed 42 --interval 0.1
```

Use `uv run` instead of activating the project virtual environment. It resolves
the Python version declared by the repository even when pyenv does not have
that version installed globally.

The default `normal` mode never injects faults. In `faulty` mode, all unaffected
assets keep reporting healthy readings while the selected asset is faulty.
