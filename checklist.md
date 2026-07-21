# Implementation Checklist

This checklist turns the project goals in [context.md](context.md), [PROBLEM.md](PROBLEM.md), and [README.md](README.md) into an execution plan. Items are checked only when they exist and have been verified in the repository.

## Product and Documentation

- [x] Define the industrial alarm-fatigue problem and safety rationale.
- [x] Define the confidence-aware, abstention-first product goal.
- [x] Document the two core demo outcomes: known precedent and human escalation.
- [x] Write a project README with architecture, fault scenarios, quick start, and roadmap.
- [x] Create structured project context, decision policy, observability plan, and delivery priorities.
- [x] Update the README status table to reflect the implemented stream processor and dashboard mockup.
- [ ] Add screenshots or a short GIF of the dashboard and SigNoz views.
- [ ] Add an AI-assistance disclosure and final hackathon submission details.

## Simulator and Raw Data

- [x] Simulate six named water-treatment assets over TCP.
- [x] Emit temperature, humidity, and vibration readings as JSON Lines.
- [x] Simulate vibration spike, gradual drift, random missing data, and duplicate data modes.
- [x] Provide a runnable producer and a live consumer.
- [x] Provide a simulator end-to-end TCP check.
- [x] Add `event_id` and `sequence_number` to every reading.
- [x] Add asset identity, equipment, area, sensor type, and unit to every reading.
- [x] Add deterministic random-seed support.
- [x] Add normal/faulty producer modes with seeded transient fault scheduling.
- [ ] Add a fast, judge-friendly demo mode.

## Ingestion and Stream Processing

- [x] Connect to the simulator TCP stream.
- [x] Parse newline-delimited JSON into a shared `SensorReading` schema.
- [x] Reconnect with exponential backoff after connection failures.
- [x] Maintain independent detector state for every device.
- [x] Process the live stream into `AnomalyEvent` objects.
- [x] Implement rolling z-score spike detection.
- [x] Implement gradual-drift detection.
- [x] Detect sustained missing vibration readings.
- [x] Detect duplicate readings from the stream flag.
- [x] Validate event IDs, sequence gaps, and stale timestamps.
- [ ] Add rate-of-change detection.
- [ ] Add Isolation Forest after deterministic detectors have tests.
- [x] Ensure detector inputs never use simulator ground-truth fields (`fault_type`, `fault_active`, `duplicate`).

## Incidents and Decision Policy

- [x] Aggregate repeated anomaly events into one incident.
- [x] Store incident first/last seen time, peak value, score, detector agreement, and affected-reading count.
- [x] Implement incident states: `OPEN`, `INVESTIGATING`, `RECOMMENDED`, `ESCALATED`, and `RESOLVED`.
- [x] Add cooldown and resolution rules to prevent alert floods.
- [x] Split `EQUIPMENT_CONDITION` and `DATA_QUALITY` incidents.
- [x] Add an application-level confidence score.
- [x] Implement `RECOMMEND`, `ESCALATE`, `MONITOR`, and `DATA_QUALITY_ALERT` decisions.
- [x] Enforce the invariant that a recommendation cannot be issued below the configured threshold.
- [x] Record abstention reason codes.

## Knowledge Base, Retrieval, and AI Explanation

- [ ] Create 20–30 structured historical incidents.
- [ ] Include verified bearing wear, shaft misalignment, overheating, sensor/gateway failure, and unrelated records.
- [ ] Persist the knowledge base in a vector store.
- [ ] Filter retrieval by equipment type, sensor type, and incident category.
- [ ] Return the top three precedents with scores and structured metadata.
- [ ] Handle empty retrieval results safely.
- [ ] Persist selected precedent IDs with the final decision.
- [ ] Add a bounded LLM explanation layer with structured output.
- [ ] Prevent the LLM from overriding the decision policy.
- [ ] Escalate safely on model/provider failures.

## Observability and SigNoz

- [ ] Create the `investigate_sensor_anomaly` root trace.
- [ ] Instrument ingestion, validation, detectors, aggregation, retrieval, confidence calculation, LLM, policy, and escalation spans.
- [ ] Propagate trace IDs through logs and API responses.
- [ ] Emit sensor, anomaly, retrieval, decision, latency, token, and override metrics.
- [ ] Send structured logs for validation failures, incidents, retrieval, recommendations, abstentions, and escalations.
- [ ] Build Industrial Operations, Agent Decision Quality, and AI Pipeline Performance dashboards in SigNoz.
- [ ] Configure safety-policy, sensor-silence, duplicate-burst, latency, error-rate, and abstention-rate alerts.
- [ ] Implement one useful SigNoz MCP investigation workflow.

## API and Operator Dashboard

- [x] Create a dark, factory-operator dashboard mockup.
- [x] Organize dashboard code into shared types, mock data, focused components, page state, and styling.
- [x] Align dashboard mock sensor fields with the simulator schema.
- [x] Support sensor selection, severity filtering, and a mock maintenance-review action.
- [x] Build the dashboard successfully with Vite.
- [x] Create FastAPI endpoints for fleet status, sensor detail, incident history, policy configuration, and review actions.
- [x] Replace dashboard mock arrays with API snapshots and live SSE data.
- [ ] Show detector outputs, retrieval evidence, confidence breakdown, and abstention reason.
- [ ] Link each incident to its SigNoz trace.
- [ ] Add a human-review queue and resolution workflow.

## Testing and Demo Readiness

- [x] Include simulator consumer and end-to-end test scripts.
- [x] Verify the dashboard production build.
- [x] Add unit tests for spike, drift, missing-data, and duplicate detectors.
- [x] Add ingestion validation and reconnect tests.
- [ ] Add retrieval tests for known and novel incidents.
- [x] Add confidence-threshold and safety-policy tests.
- [x] Add end-to-end tests for normal operation, transient faults, and data quality.
- [ ] Add trace-creation verification.
- [ ] Add Docker Compose, `.env.example`, Foundry configuration, and pinned dependencies.
- [ ] Verify a clean-clone, one-command demo.
- [ ] Record a backup demo video.

## Next Milestone

The highest-value next slice is: **incident knowledge retrieval → confidence/abstention policy integration → OpenTelemetry trace**. The deterministic two-mode fleet now provides the live fault stream for that work.
