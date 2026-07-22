# Industrial IoT Anomaly Control

> An evidence-first industrial diagnosis system that detects equipment faults, retrieves verified precedents, explains safe maintenance actions, and abstains when the evidence is weak.

Industrial plants already generate continuous vibration, temperature, humidity, and transport telemetry. Conventional threshold alarms can say that a value is high, but they rarely explain why it matters. The result is alarm fatigue, missed failures, and maintenance decisions made without enough context.

Industrial IoT Anomaly Control is designed to turn that raw stream into a traceable operational decision. It combines deterministic detection, historical-incident retrieval, application-owned confidence policy, bounded AI explanation, human review, and end-to-end observability. The system recommends action only when verified evidence is strong enough; otherwise, it explicitly escalates instead of guessing.

## Final product architecture

```text
Six-asset water-treatment simulator
                │ TCP JSON Lines
                ▼
Validated ingestion and per-device state
                │
                ├── deterministic signal detectors
                ├── statistical anomaly detection
                └── transport and data-quality checks
                │
                ▼
Incident aggregation and lifecycle
                │
                ▼
Filtered historical-incident retrieval
                │ top precedents + similarity + verification
                ▼
Application-owned confidence and abstention policy
                │
        ┌───────┴────────┐
        ▼                ▼
   RECOMMEND          ESCALATE
        │                │
        ▼                ▼
Bounded AI         Human-review
explanation           queue
        └───────┬────────┘
                ▼
FastAPI + operator dashboard + OpenTelemetry/SigNoz
```

The LLM does not decide whether maintenance should be recommended. It explains a decision already approved by application policy and cannot override confidence thresholds, data-quality gates, or abstention rules.

## What the finished system does

1. Streams realistic telemetry from six named assets in a water-treatment plant.
2. Validates event identity, sequence, timestamps, schema, and channel values at ingestion.
3. Detects vibration spikes, gradual drift, dropouts, rate changes, multivariate anomalies, and transport-quality failures using independent per-device state.
4. Groups related detector evidence into one incident instead of flooding operators with repeated alarms.
5. Retrieves only relevant historical incidents after filtering by equipment, sensor type, and incident category.
6. Calculates confidence from anomaly strength, detector agreement, retrieval similarity and margin, precedent verification, persistence, and data quality.
7. Recommends a bounded maintenance action when evidence passes policy, or creates a human-review escalation with explicit reason codes when it does not.
8. Produces an operator-facing explanation that cites detector evidence and retrieved precedents without changing the policy decision.
9. Traces the entire investigation through OpenTelemetry and SigNoz, including latency, retrieval, confidence, model usage, outcome, and operator action.
10. Records review outcomes so verified resolutions can improve the historical incident knowledge base.

## Three safe outcome paths

### 1. Verified precedent → maintenance recommendation

A pump begins developing a bearing-wear signature. The detectors identify persistent vibration drift and supporting spike evidence, and the incident service correlates those events into one equipment-condition investigation.

Retrieval finds a strong, verified historical match such as `INC-0092`. The similarity, match margin, detector agreement, data quality, and precedent status satisfy policy. The system recommends a bearing inspection within a bounded time window, cites the supporting incident, and generates a concise operator explanation.

### 2. Weak or novel evidence → human escalation

An asset produces a genuine anomaly, but the knowledge base has no sufficiently similar verified precedent—or the top matches are ambiguous. The system does not ask the model to invent a cause.

Policy returns `ESCALATE`, records reason codes such as `NO_MATCHING_PRECEDENT`, `LOW_RETRIEVAL_SIMILARITY`, `AMBIGUOUS_MATCHES`, or `UNVERIFIED_PRECEDENT`, and places the incident in the human-review queue.

### 3. Poor stream evidence → data-quality alert

Missing readings, duplicate event IDs, sequence gaps, timestamp regressions, stale messages, or gateway failures create a `DATA_QUALITY` incident. The system recommends inspection of the sensor, publisher, gateway, network, or ingestion path—not a mechanical repair.

Data-quality incidents can never become equipment recommendations merely because their messages look abnormal.

## Water-treatment demonstration fleet

| Stream ID | Asset | Equipment | Plant area |
| --- | --- | --- | --- |
| `sensor-1` | `P-101` | Raw Water Intake Pump | Intake Station |
| `sensor-2` | `B-201` | Aeration Blower | Biological Treatment |
| `sensor-3` | `M-301` | Flash Mixer | Coagulation Basin |
| `sensor-4` | `C-401` | Sludge Dewatering Centrifuge | Solids Handling |
| `sensor-5` | `P-501` | Chemical Dosing Pump | Chemical Room |
| `sensor-6` | `SC-601` | Sludge Screw Conveyor | Dewatering Area |

Every reading carries the stream identity, asset tag, equipment name and type, plant area, sequence and event identity, timestamp, temperature, humidity, and vibration.

## Simulator modes

Operators manage two plant modes rather than hand-authoring individual fault scenarios:

| Mode | Behavior |
| --- | --- |
| `normal` | All six assets continuously emit healthy telemetry with natural measurement noise |
| `faulty` | A seeded scheduler selects a compatible transient fault, affected asset, severity, and duration; the asset then recovers automatically |

Faulty mode can produce cavitation, bearing degradation, overheating, shaft or rotor imbalance, mechanical overload, intermittent sensor operation, duplicate events, and sequence gaps. Unaffected assets continue operating normally.

Using the same `--seed` reproduces scheduling and telemetry decisions. Playback speed can change through `--interval` without changing the reading-based fault schedule.

## Evidence and decision ownership

| Layer | Responsibility |
| --- | --- |
| Simulator | Emit realistic telemetry and delivery behavior; never create incidents directly |
| Ingestion | Parse and validate readings, reconnect safely, and reject malformed input |
| Detectors | Identify observable signal anomalies and transport-quality failures |
| Incident service | Correlate events, maintain lifecycle, and prevent alert floods |
| Retrieval | Return relevant historical precedents with scores and verification metadata |
| Confidence policy | Own `MONITOR`, `RECOMMEND`, `ESCALATE`, and `DATA_QUALITY_ALERT` decisions |
| LLM explanation | Explain an approved decision using bounded evidence; never override policy |
| Human review | Confirm, correct, or resolve uncertain outcomes |
| SigNoz | Make every stage inspectable through traces, metrics, logs, dashboards, and alerts |

The final confidence calculation combines:

- anomaly strength and persistence;
- detector agreement;
- input data quality;
- top retrieval similarity;
- separation between the first and second retrieval matches;
- verified-precedent status;
- configured recommendation and abstention thresholds.

The critical invariant is:

```python
assert not (decision == "RECOMMEND" and confidence < configured_threshold)
```

The application enforces that invariant before an explanation or notification is dispatched.

## Final operator experience

The completed dashboard will provide:

- live state, readings, freshness, and bounded trends for all six plant assets;
- detector evidence and incident lifecycle without storing every normal reading;
- retrieved precedents, similarity scores, verification status, and cited resolutions;
- confidence components, final policy decision, and abstention reason codes;
- a bounded AI explanation and proposed maintenance action;
- separate equipment-condition and data-quality workflows;
- acknowledgement, human-review, override, resolution, and outcome capture;
- runtime policy controls with validation and audit history;
- a direct link from every investigation to its SigNoz trace.

Normal telemetry remains ephemeral. The final system persists only operationally meaningful records: incidents, evidence, selected precedents, decisions, explanations, traces, review actions, and confirmed outcomes.

## Observability and safety

Every investigation produces an `investigate_sensor_anomaly` root trace with spans for:

```text
ingest → validate → update sensor state → detect → aggregate incident
→ filter candidates → retrieve precedents → calculate confidence
→ apply policy → invoke explanation model → recommend or escalate
→ record operator outcome
```

Trace attributes connect the sensor, equipment, incident, detector evidence, retrieval results, confidence, decision, abstention reason, model usage, and operator outcome.

The final SigNoz experience includes:

- an Industrial Operations dashboard for throughput, anomalies, open incidents, sensor silence, and data quality;
- an Agent Decision Quality dashboard for recommendations, abstentions, confidence, retrieval strength, and human overrides;
- an AI Pipeline Performance dashboard for end-to-end latency, retrieval and model latency, tokens, errors, and failed investigations;
- alerts for sensor silence, duplicate bursts, repeated empty retrieval, model failures, high latency, unusual abstention rates, and any safety-policy violation.

## Final API and contracts

The finished API builds on the current REST and SSE surface with investigation intelligence and human review.

| Area | Final capability |
| --- | --- |
| Fleet | Live fleet snapshot, selected asset detail, trends, freshness, and stream status |
| Incidents | Filtered history, detector evidence, lifecycle, acknowledgement, and resolution |
| Investigations | Retrieved precedents, confidence breakdown, final decision, reason codes, and explanation |
| Human review | Review queue, assignment, outcome, correction, and verified resolution |
| Policy | Versioned detector, retrieval, confidence, abstention, and notification settings |
| Observability | Trace identifiers and links attached to investigations and decisions |
| Live updates | SSE events for readings, incidents, investigations, policy, reviews, and stream health |

The currently implemented routes are listed in [Current runnable system](#current-runnable-system).

## Example sensor reading

```json
{
  "event_id": "sensor-1-evt-000123",
  "sequence_number": 123,
  "device_id": "sensor-1",
  "asset_id": "P-101",
  "equipment_name": "Raw Water Intake Pump",
  "equipment_type": "centrifugal_pump",
  "area": "Intake Station",
  "sensor_type": "vibration",
  "unit": "mm/s",
  "timestamp": 1784678400.123,
  "temperature": 24.18,
  "humidity": 61.72,
  "vibration": 0.31,
  "fault_type": null,
  "fault_active": false,
  "duplicate": false
}
```

`fault_type`, `fault_active`, and `duplicate` are simulator evaluation metadata. Detection and decision code uses only observable telemetry and delivery behavior.

## Current runnable system

The repository already contains the complete streaming, detection, incident, API, and live-dashboard foundation. RAG, LLM explanations, full review persistence, and SigNoz are the remaining product layers.

### Requirements

- [uv](https://docs.astral.sh/uv/) with project-managed Python 3.13+
- [Bun](https://bun.sh/) for the React dashboard

Use `uv run` for Python commands so a matching global pyenv interpreter is not required.

Install dependencies:

```bash
uv sync --dev
cd dashboard
bun install
cd ..
```

Start the current system in three terminals from the repository root:

```bash
# Terminal 1 — water-treatment telemetry and transient faults
cd iot-streaming-mock
uv run main.py produce --mode faulty --seed 42 --interval 0.1
```

```bash
# Terminal 2 — ingestion, detection, incidents, REST API, and SSE
uv run uvicorn --app-dir src iot_stream.api.main:app --reload
```

```bash
# Terminal 3 — live operator dashboard
cd dashboard
bun run dev
```

Open:

- Dashboard: `http://localhost:5173`
- API: `http://127.0.0.1:8000`
- Interactive API documentation: `http://127.0.0.1:8000/docs`

Use `--mode normal` for a healthy plant stream. The optional raw consumer can observe the broadcast alongside the API:

```bash
cd iot-streaming-mock
uv run main.py consume --json
```

### Currently implemented API routes

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | API, upstream stream, fleet, and incident status |
| `GET` | `/api/sensors` | Current fleet snapshots and bounded trends |
| `GET` | `/api/sensors/{device_id}` | One live sensor snapshot |
| `GET` | `/api/incidents` | Incidents filtered by optional state or category |
| `GET` | `/api/incidents/{incident_id}` | One incident |
| `GET` | `/api/activity` | Recent bounded runtime activity |
| `GET` | `/api/policy` | Current runtime detector policy |
| `PUT` | `/api/policy` | Validate and apply runtime policy changes |
| `POST` | `/api/incidents/{incident_id}/acknowledge` | Acknowledge an incident |
| `POST` | `/api/incidents/{incident_id}/resolve` | Resolve an incident manually |
| `GET` | `/api/stream` | Server-Sent Events for live dashboard updates |

Current readings, bounded trends, incidents, activity, and policy settings are in memory and reset when the API restarts.

## Current progress

Last reconciled with the repository on **2026-07-22**.

| Capability | State |
| --- | --- |
| Six named water-treatment assets | Complete |
| Normal and seeded faulty operating modes | Complete |
| Equipment-aware transient faults and automatic recovery | Complete |
| TCP broadcast, validated ingestion, and reconnection | Complete |
| Per-device spike, drift, dropout, and transport-quality detection | Complete |
| Incident aggregation, lifecycle, confidence, and detector-agreement policy | Complete |
| FastAPI snapshots, policy operations, incident actions, and SSE | Complete |
| Live six-asset dashboard with runtime policy controls | Complete |
| Structured historical incident knowledge base | Next milestone |
| Filtered retrieval and retrieval-aware confidence | Next milestone |
| Bounded LLM explanation and explicit abstention workflow | Planned |
| Persistent human-review outcomes | Planned |
| OpenTelemetry instrumentation and SigNoz experience | Planned |
| Docker/Foundry packaging and clean-clone demo | Planned |

The latest verified baseline is **37 passing Python tests**, a successful dashboard lint and production build, and a real TCP smoke run that delivered readings for all six assets.

## Project structure

```text
.
├── iot-streaming-mock/
│   └── simulator/          # Fleet catalog, producer, scheduler, faults, and TCP tools
├── src/iot_stream/
│   ├── ingestion/          # TCP validation and reconnection
│   ├── pipeline/           # Signal and transport-quality detectors
│   ├── incidents/          # Aggregation, lifecycle, confidence, and policy
│   └── api/                # FastAPI runtime, REST routes, and SSE
├── dashboard/src/          # React operator dashboard and live API client
├── test/                   # Unit, contract, policy, API, and integration tests
├── docs/superpowers/specs/ # Approved milestone designs
├── context.md              # Final product, safety, and observability requirements
└── PROBLEM.md              # Product problem and differentiator
```

## Verification

```bash
# Python tests
uv run python -m unittest discover -v

# Simulator TCP integration check
cd iot-streaming-mock
uv run main.py e2e

# Dashboard checks
cd ../dashboard
bun run lint
bun run build
```

## Final definition of done

The proposed product is complete when:

- a clean clone can run the three outcome paths deterministically;
- a known fault recommends maintenance only when a strong, verified precedent satisfies policy;
- a weak, ambiguous, novel, or unverified match produces explicit abstention and human escalation;
- data-quality failures never become mechanical diagnoses;
- every recommendation cites detector evidence and retrieved incident IDs;
- the LLM cannot override application policy or invent missing evidence;
- each investigation is traceable end to end in SigNoz;
- operators can review, correct, resolve, and record verified outcomes;
- tests cover retrieval, confidence thresholds, abstention, model failure, trace creation, and full end-to-end behavior;
- setup, configuration, AI-assistance disclosure, dashboards, and demo assets are reproducible from documentation.

## Guiding principle

**A system that knows when it does not know is safer than one that always sounds certain.**
