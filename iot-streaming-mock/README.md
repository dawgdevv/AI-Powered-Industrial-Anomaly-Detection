# IoT Streaming Mock

A dependency-free TCP simulator for temperature, humidity, and vibration
telemetry. It emits newline-delimited JSON from multiple devices.

```bash
./.venv/bin/python main.py produce
./.venv/bin/python main.py consume --json
```

Repeatable demo scenarios accept a seed:

```bash
./.venv/bin/python main.py produce --scenario known_fault --seed 42 --interval 0.1
./.venv/bin/python main.py produce --scenario novel_fault --seed 42 --interval 0.1
./.venv/bin/python main.py produce --scenario data_quality --seed 42 --interval 0.1
```

Calling `.venv/bin/python` directly avoids conflicts when pyenv cannot see
the Python interpreter installed and managed by uv.

The default `random` scenario retains the original rotating spike, drift,
missing-data, and duplicate-data fault modes.
