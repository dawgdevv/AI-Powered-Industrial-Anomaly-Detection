# AI-Powered Industrial Anomaly Detection

> Detect abnormal industrial sensor behaviour in real time, explain likely causes using past incidents, and escalate uncertain cases to a human expert.

Industrial equipment produces a continuous stream of telemetry—vibration, temperature, humidity, and more. Traditional threshold alarms can spot that a value is high, but they cannot explain why it matters. The result is noisy alerts, alarm fatigue, and faults that are missed until they cause unplanned downtime.

This project is an end-to-end prototype for **real-time industrial anomaly detection and confidence-aware diagnosis**. It combines simulated IoT data, streaming anomaly detection, retrieval-augmented generation (RAG), and observability to turn raw readings into actionable incident intelligence.

## Why this matters

On a factory floor, an incorrect AI diagnosis is not merely an unhelpful answer—it can create a safety and liability risk. This system is designed to make a recommendation only when the evidence supports it. When there is no sufficiently similar historical incident, it explicitly escalates the case for human review instead of guessing.

## How it works

```text
IoT sensor simulator
        |
        v
Live TCP sensor stream
        |
        v
Stream processor + anomaly detection
        |
        v
RAG incident retrieval + AI reasoning
        |
        v
Confident recommendation OR human escalation
        |
        v
Traces, API, and dashboard
```

The planned system flow is:

1. Simulate a fleet of industrial IoT sensors that send live JSON readings over TCP.
2. Detect unusual patterns with rolling statistics and Isolation Forest.
3. Retrieve similar, previously resolved incidents from a knowledge base.
4. Use an AI agent to explain the probable cause and recommended next action.
5. Apply a confidence threshold: diagnose when evidence is strong; escalate when it is not.
6. Trace decisions, latency, confidence, and outcomes for observability.

## A real-world example

At 2am, a pump's vibration climbs from a normal baseline of `0.2` to `2.8`—a 14× increase.

- A conventional alarm reports only that the threshold was crossed.
- This system flags the anomaly, looks up similar incidents, and can produce an evidence-based alert such as: _"Sensor-4 matches the early bearing-wear signature from incident #0092. Recommend inspection within 48 hours."_
- If the pattern is novel or the retrieval result is weak, it responds: _"No matching precedent; confidence is below threshold. Escalating for human review."_

## Simulated fault scenarios

The included simulator models four realistic vibration-data failure modes rather than generic random noise:

| Fault mode | What it simulates |
| --- | --- |
| `anomaly` | Sudden positive vibration spikes |
| `drift` | Gradual value drift after a sustained period |
| `MCAR` | Missing readings occurring at random |
| `duplicate_data` | Duplicate sensor readings |

Each reading includes a device ID, timestamp, temperature, humidity, vibration, fault metadata, and duplicate indicator.

## Quick start: run the live simulator

Requirements: Python 3.13+.

Start the producer in one terminal:

```bash
cd iot-streaming-mock
python main.py produce
```

In a second terminal, connect a consumer:

```bash
cd iot-streaming-mock
python main.py consume
```

The producer starts a TCP server on `0.0.0.0:9999` and emits readings from four simulated devices approximately every 0.5 seconds. To receive JSON Lines suitable for a downstream stream processor, use:

```bash
python main.py consume --json
```

You can also run the simulator's end-to-end check:

```bash
cd iot-streaming-mock
python main.py e2e
```

For a repeatable demo, choose a named scenario and seed:

```bash
./.venv/bin/python main.py produce --scenario known_fault --seed 42 --interval 0.1
./.venv/bin/python main.py produce --scenario novel_fault --seed 42 --interval 0.1
./.venv/bin/python main.py produce --scenario data_quality --seed 42 --interval 0.1
```

## Example reading

```json
{
  "event_id": "sensor-1-evt-000123",
  "sequence_number": 123,
  "device_id": "sensor-1",
  "equipment_type": "centrifugal_pump",
  "sensor_type": "vibration",
  "unit": "mm/s",
  "timestamp": 1730000000.123,
  "temperature": 22.41,
  "humidity": 51.82,
  "vibration": 0.24,
  "fault_type": "anomaly",
  "fault_active": false,
  "duplicate": false
}
```

## Project structure

```text
.
├── iot-streaming-mock/       # Runnable TCP-based IoT sensor simulator
│   └── simulator/            # Producer, consumer, schemas, and fault models
├── src/iot_stream/
│   ├── ingestion/            # TCP stream ingestion
│   ├── pipeline/             # Stream processing and anomaly detectors
│   ├── incidents/            # Aggregation, confidence, and decisions
│   └── api/                  # Future FastAPI service
├── test/                     # Unit and milestone integration tests
└── PROBLEM.md                # Problem statement and product context
```

## Project status

| Component | Status |
| --- | --- |
| IoT simulator with four fault modes | Complete |
| TCP broadcast and live consumer | Complete |
| Validated ingestion and stream processor | Complete |
| Deterministic anomaly and transport-quality detection | Complete |
| Incident aggregation and detector-agreement policy | Complete |
| Incident knowledge base and RAG retrieval | Planned |
| Confidence-aware AI diagnosis and escalation | Planned |
| OpenTelemetry/Signoz observability | Planned |
| FastAPI service with REST and SSE | Complete |
| Live operator dashboard | Complete |

## Technology direction

- **Streaming:** TCP JSON Lines
- **Detection:** rolling z-scores and Isolation Forest
- **Knowledge retrieval:** vector store (Chroma)
- **Reasoning:** LLM agent with an explicit abstention rule
- **Observability:** OpenTelemetry and SigNoz
- **Service layer:** FastAPI

## Guiding principle

**A system that knows when it does not know is safer than one that always sounds certain.**

## Run tests

The Python suite uses only the standard library:

```bash
python -m unittest discover -v
```

## Run the live API and dashboard

Start the three runtime processes in separate terminals.

```bash
# Terminal 1 — TCP sensor producer
cd iot-streaming-mock
./.venv/bin/python main.py produce --scenario random --seed 42 --interval 0.1
```

```bash
# Terminal 2 — FastAPI processing service
./.venv/bin/uvicorn --app-dir src iot_stream.api.main:app --reload
```

```bash
# Terminal 3 — React operator dashboard
cd dashboard
bun run dev
```

Open `http://localhost:5173`. The API is available at
`http://127.0.0.1:8000`, with interactive route documentation at
`http://127.0.0.1:8000/docs`.

The API keeps current sensor trends, incidents, activity, and policy settings
in memory only. Runtime policy changes and operator actions reset when the API
restarts.
