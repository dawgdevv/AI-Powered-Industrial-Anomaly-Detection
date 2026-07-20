# Project Context — AI-Powered Industrial Anomaly Detection

## 1. Purpose

Build a focused, observable industrial-diagnosis workflow for the **AI & Agent Observability** track.

> An industrial diagnosis agent that traces the evidence behind each recommendation and escalates to a human when evidence is weak.

The product is not a full industrial platform. Its job is to demonstrate two safe, believable workflows:

1. A known pump-bearing issue is detected, matched to a verified historical incident, and produces a confident maintenance recommendation.
2. A novel or weakly matched issue is detected, and the system abstains and creates a human-review escalation.

## 2. Product Principles

- **Safety first:** the application, not the LLM, enforces the final decision policy.
- **Evidence over confidence:** every recommendation must cite detector results and retrieved incidents.
- **Abstain when uncertain:** no plausible precedent, poor data quality, or ambiguous matches result in escalation.
- **Observable by default:** a single trace explains the journey from raw sensor reading to final decision.
- **Focused demo:** avoid unrelated infrastructure until the two core scenarios are complete.

Do not add Kafka, Kubernetes, authentication, multiple agents, or complex deployment before the end-to-end demo works.

## 3. Users and Jobs

| User | Need | Dashboard outcome |
| --- | --- | --- |
| Factory operator | Understand what changed and what to do next | Fleet status, incident explanation, recommended action |
| Maintenance engineer | Validate a diagnosis and plan work | Evidence, matching incidents, equipment timeline |
| Reviewer/judge | Trust the agent’s behavior | End-to-end trace, policy decision, metrics, logs, alert |

## 4. System Overview

```text
IoT simulator → Stream ingestion → Deterministic detectors → Incident aggregation
     → Filtered RAG retrieval → Confidence policy → LLM explanation
     → Recommendation or human escalation → SigNoz + operator dashboard
```

### Decision ownership

| Layer | Responsibility |
| --- | --- |
| Detectors | Identify signal anomalies and data-quality failures |
| Incident service | Group repeated abnormal readings into a single incident |
| Retrieval | Find comparable, relevant historical incidents |
| Confidence policy | Decide `RECOMMEND`, `ESCALATE`, `MONITOR`, or `DATA_QUALITY_ALERT` |
| LLM | Explain an already-approved decision; never override policy |
| SigNoz | Make every stage inspectable through traces, metrics, logs, dashboards, and alerts |

## 5. Required Demo Scenarios

### Scenario A — Known bearing wear

- Simulate a pump-vibration drift.
- Detect the anomaly and aggregate an equipment-condition incident.
- Retrieve verified incident `INC-0092` as the strongest precedent.
- Meet the confidence threshold and recommend a bearing inspection within 48 hours.
- Show the linked trace in SigNoz.

### Scenario B — Novel fault

- Simulate a pattern with no close, verified precedent.
- Detect the anomaly but return weak or ambiguous retrieval results.
- Apply the abstention policy and create a human-review incident.
- Show the abstention reason, trace, and alert.

### Scenario C — Data-quality failure

- Simulate missing readings or duplicate messages.
- Create a `DATA_QUALITY` alert, not a mechanical-fault diagnosis.
- Recommend inspection of the sensor, gateway, network, or ingestion path.

## 6. Data Contracts

### Raw sensor reading

The simulator emits newline-delimited JSON over TCP. Detection must not use hidden fault labels.

```json
{
  "event_id": "evt-000123",
  "sequence_number": 123,
  "device_id": "sensor-4",
  "equipment_type": "centrifugal_pump",
  "sensor_type": "vibration",
  "unit": "mm/s",
  "timestamp": 1730000000.123,
  "temperature": 22.41,
  "humidity": 51.82,
  "vibration": 0.24,
  "fault_type": "drift",
  "fault_active": false,
  "duplicate": false
}
```

`fault_type`, `fault_active`, and `duplicate` are simulator ground truth only. The anomaly detector must infer conditions from observable data; duplicate and missing-message checks are transport/data-quality rules.

### Standard detector result

```json
{
  "sensor_id": "sensor-4",
  "detector": "rolling_zscore",
  "anomalous": true,
  "score": 0.91,
  "reason": "Vibration is 5.4 standard deviations above baseline",
  "observed_value": 1.82,
  "baseline_mean": 0.23,
  "baseline_std": 0.29
}
```

### Incident categories

| Category | Examples | Action |
| --- | --- | --- |
| `EQUIPMENT_CONDITION` | vibration spike, gradual drift, overheating | retrieve equipment precedents and assess maintenance action |
| `DATA_QUALITY` | missing readings, duplicate events, stale timestamps | inspect the sensor, gateway, network, or ingestion path |

### Incident lifecycle

`OPEN` → `INVESTIGATING` → `RECOMMENDED` or `ESCALATED` → `RESOLVED`

An incident opens when abnormality begins, updates while it continues, records peak value and detector agreement, and resolves only after several normal windows. Cooldowns prevent alert floods.

## 7. Detection and Retrieval

### Detection order

1. Validate schema, timestamps, event IDs, and sequence numbers.
2. Maintain an independent rolling baseline for every sensor.
3. Detect missing data, duplicate event IDs, and stale timestamps.
4. Run deterministic anomaly detectors: rolling z-score, rate of change, and gradual drift.
5. Add Isolation Forest only after deterministic detection is reliable.
6. Emit standard detector results and aggregate them into incidents.

### Knowledge base

Create 20–30 concise, structured historical incidents. Include verified and unverified examples across bearing wear, shaft misalignment, overheating, sensor/gateway failures, and deliberately unrelated records.

Each record needs equipment type, sensor type, pattern, observed values, cause, resolution, recommendation, and human-confirmed outcome.

### Retrieval rules

1. Filter by equipment type, sensor type, and incident category.
2. Retrieve the top three relevant incidents with scores and metadata.
3. Store retrieved incident IDs on the final decision.
4. Handle empty retrieval explicitly—never substitute an unrelated precedent.

## 8. Confidence and Abstention Policy

Calculate confidence in application code from anomaly strength, retrieval similarity, first/second-match margin, detector agreement, data quality, and verified-precedent status.

```python
if data_quality_score < 0.60:
    decision = "DATA_QUALITY_ALERT"
elif anomaly_score < 0.65:
    decision = "MONITOR"
elif top_similarity < 0.78:
    decision = "ESCALATE"
elif top_similarity - second_similarity < 0.08:
    decision = "ESCALATE"
elif not top_incident_verified:
    decision = "ESCALATE"
else:
    decision = "RECOMMEND"
```

Reason codes: `NO_MATCHING_PRECEDENT`, `LOW_RETRIEVAL_SIMILARITY`, `AMBIGUOUS_MATCHES`, `POOR_SENSOR_DATA`, `UNVERIFIED_PRECEDENT`, and `DETECTOR_DISAGREEMENT`.

Critical invariant:

```python
assert not (decision == "RECOMMEND" and confidence < configured_threshold)
```

## 9. Observability Plan

### Root trace

Create one trace per investigation: `investigate_sensor_anomaly`.

Required spans:

```text
ingest_sensor_reading → validate_sensor_reading → update_sensor_window
→ run_zscore_detector / run_drift_detector / run_isolation_forest
→ aggregate_incident → filter_incident_candidates → retrieve_similar_incidents
→ calculate_decision_confidence → invoke_llm → apply_abstention_policy
→ dispatch_recommendation or create_human_escalation
```

Required attributes include `sensor.id`, `sensor.type`, `equipment.type`, `incident.id`, `incident.type`, `anomaly.score`, `retrieval.top_similarity`, `retrieval.margin`, `agent.confidence`, `agent.decision`, `agent.abstained`, `agent.abstention_reason`, and LLM model/token attributes.

### Metrics and logs

Track readings, invalid/duplicate/missing data, anomalies, open incidents, retrieval outcomes and latency, recommendations, abstentions, escalations, human overrides, decision latency, token use, and error rate.

Every structured log must include `trace_id`, `incident_id` when available, and `sensor_id`. Never log secrets or full sensitive prompts.

### SigNoz dashboards and alerts

| Dashboard | Key views |
| --- | --- |
| Industrial operations | readings, anomalies by sensor, open incidents, missing/duplicate data, detection latency |
| Agent decision quality | recommendations vs abstentions, confidence, reasons, retrieval similarity/margin, overrides |
| AI pipeline performance | end-to-end/retrieval/LLM latency, tokens, errors, failed investigations |

Alert on sensor silence, duplicate bursts, excessive anomaly rate, repeated empty retrieval, high LLM latency/failure, rising abstention rate, excessive end-to-end latency, and any recommendation below the confidence threshold.

## 10. Dashboard Scope

The operator dashboard is intentionally limited to:

- live fleet status and current readings;
- selected-sensor trend and data-quality state;
- incident evidence, retrieved precedent, confidence, and final decision;
- human-review queue with escalation reason;
- a link to the corresponding SigNoz trace.

The current React mock dashboard keeps simulator-aligned data in `dashboard/src/data/mockDashboardData.ts`; replace those arrays with API data once the backend is ready.

## 11. Delivery Plan

| Phase | Deliverables |
| --- | --- |
| 1. Detection | deterministic simulator, ingestion, validation, rolling baselines, detector results |
| 2. Incident intelligence | aggregation, persistence, knowledge base, filtered retrieval |
| 3. Safe agent | confidence policy, abstention, bounded LLM explanation, escalation |
| 4. SigNoz | OpenTelemetry spans, logs, metrics, dashboards, alerts, MCP investigation workflow |
| 5. Demo and submission | Docker/Foundry reproducibility, dashboard, tests, screenshots, README, blog, video |

## 12. Definition of Done

- The three deterministic demo scenarios run from a clean clone.
- Known fault recommends only with strong, verified evidence.
- Novel fault escalates with an explicit reason.
- Data-quality faults do not become mechanical diagnoses.
- Every decision is traceable in SigNoz.
- The dashboard makes evidence and uncertainty understandable to an operator.
- Setup, configuration, AI-assistance disclosure, and implementation claims are honest and reproducible.

## 13. Priority Order

When time is limited, preserve work in this order:

1. End-to-end known-fault case
2. End-to-end abstention case
3. Complete SigNoz trace
4. Metrics, logs, dashboard, and alert
5. Reproducible Foundry setup
