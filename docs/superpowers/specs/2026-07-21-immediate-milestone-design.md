# Immediate Milestone Design

## Scope

This milestone delivers a deterministic, testable path from simulated sensor readings to an incident decision. It includes:

- an expanded and validated sensor-reading contract;
- deterministic simulator scenarios;
- tested ingestion and deterministic anomaly detectors;
- incident aggregation and lifecycle handling; and
- a confidence and abstention policy based only on detector agreement.

RAG retrieval, LLM explanations, OpenTelemetry, FastAPI, and live dashboard integration remain outside this milestone.

## Architecture

Validated `SensorReading` values pass through a per-device `DeviceDetectorSet`. The resulting `AnomalyEvent` values enter an `IncidentAggregator`, which separates equipment-condition events from data-quality events and groups related events for the same device. A pure `DecisionPolicy` calculates bounded confidence from relevant detector agreement and incident persistence, then returns one of `RECOMMEND`, `MONITOR`, `ESCALATE`, or `DATA_QUALITY_ALERT`.

The policy owns the decision. Future retrieval and LLM layers may supply evidence or explanations, but they will not bypass the recommendation threshold.

## Data Contract

`SensorReading` contains these required observable fields:

- `event_id`: stable unique identifier for one emitted event;
- `sequence_number`: monotonically increasing per-device sequence;
- `device_id`;
- `equipment_type`;
- `sensor_type`;
- `unit`;
- `timestamp`;
- `temperature`;
- `humidity`; and
- `vibration`.

Simulator-only `fault_type`, `fault_active`, and `duplicate` fields remain optional metadata for demonstrations and simulator assertions. Production detection must not use them. Duplicate and gap detection use event IDs and sequence numbers.

Parsing rejects missing required fields, invalid field types, non-finite numeric values, and empty identifiers. Validation failures expose structured reason codes and do not produce partially populated readings.

## Deterministic Simulator Scenarios

The simulator accepts a random seed and an explicit scenario:

- `known_fault`: produces a repeatable equipment-condition pattern that exercises spike and drift detectors;
- `novel_fault`: produces repeatable abnormal equipment behavior with insufficient detector agreement for a recommendation; and
- `data_quality`: produces repeatable sequence gaps and duplicate event IDs.

The same scenario and seed must generate the same sequence of readings. Existing free-running simulation remains the default for backward compatibility.

## Incident Aggregation

An `Incident` records:

- stable incident ID;
- device ID and category;
- lifecycle state;
- first-seen and last-seen timestamps;
- affected-reading count;
- distinct contributing detectors;
- peak severity and peak observed value;
- confidence and decision; and
- machine-readable reason codes.

Spike and drift events produce `EQUIPMENT_CONDITION` incidents. Dropout, duplicate-event, sequence-gap, and stale-reading events produce `DATA_QUALITY` incidents. Events from different categories never strengthen each other's confidence.

Related events for the same device and category update the open incident within a configured aggregation window. A quiet period closes an incident as `RESOLVED`; one normal reading cannot resolve it. Cooldown behavior prevents repeated notifications without discarding continuing evidence.

Lifecycle transitions are:

`OPEN -> INVESTIGATING -> RECOMMENDED | ESCALATED -> RESOLVED`

`MONITOR` is a decision while the incident remains `INVESTIGATING`. `DATA_QUALITY_ALERT` keeps the incident category distinct and moves it to `ESCALATED` because operator review is required.

## Weighted Detector Agreement

Confidence is deterministic and uses only detectors relevant to the incident category. Equipment confidence uses configured weights for spike and drift evidence. Data-quality detectors do not contribute to equipment confidence. Unknown detectors contribute zero weight.

The base score is the sum of distinct active detector weights divided by the total configured equipment-detector weight. Repeated events receive a small bounded persistence bonus. The final score is clamped to `[0.0, 1.0]`.

Initial policy thresholds are configuration constants:

- confidence at or above `0.75`: `RECOMMEND`;
- confidence from `0.40` through `0.749...`: `MONITOR`;
- confidence below `0.40`, conflicting evidence, or unusable equipment data: `ESCALATE`; and
- sustained data-quality evidence: `DATA_QUALITY_ALERT` regardless of equipment confidence.

The implementation enforces an invariant: `RECOMMEND` cannot be constructed when confidence is below the recommendation threshold.

## Error Handling

- Malformed JSON and invalid readings are rejected with structured validation reason codes.
- Stale timestamps, event-ID reuse, and sequence gaps create data-quality events rather than equipment diagnoses.
- Unknown detector names are retained for observability but have zero confidence weight.
- Confidence inputs and results are clamped to safe numeric bounds.
- Category mismatches never merge into an existing incident.
- Policy failures default to escalation rather than recommendation.

## Testing

Tests use Python's standard `unittest` framework so this milestone adds no test dependency. Tests remain discoverable by pytest if it is added later.

Unit coverage includes:

- spike, drift, dropout, and duplicate/sequence validation;
- valid and malformed ingestion payloads;
- required fields, invalid types, non-finite values, and stale timestamps;
- deterministic scenario reproducibility;
- aggregation, category isolation, cooldown, and quiet-period resolution;
- weighted confidence, persistence bonus, unknown detectors, and clamping; and
- the invariant preventing recommendations below the threshold.

An integration test feeds deterministic readings through detection, aggregation, and policy. It verifies a high-agreement equipment recommendation, a low-agreement abstention/monitoring outcome, and a data-quality alert.

## Acceptance Criteria

The milestone is complete when:

1. identical scenario and seed inputs generate identical readings;
2. all required reading fields are validated before pipeline entry;
3. detector tests cover all existing deterministic detectors;
4. repeated anomaly events aggregate into category-safe incidents;
5. confidence is explainable from distinct detector weights and persistence;
6. no recommendation can occur below the configured threshold;
7. data-quality evidence cannot produce a mechanical recommendation; and
8. the complete standard-library test suite and dashboard build pass.
