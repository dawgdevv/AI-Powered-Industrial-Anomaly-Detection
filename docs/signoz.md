# SigNoz traces

This application emits privacy-safe OpenTelemetry traces, metrics, and
incident lifecycle logs. It uses standard OTLP HTTP configuration, so no
SigNoz code is coupled into the incident pipeline.

## 1. Run SigNoz locally

SigNoz's current supported self-hosted Docker route uses Foundry. Install it,
then save this as `casting.yaml` outside this repository:

```yaml
apiVersion: v1alpha1
kind: Installation
metadata:
  name: signoz
spec:
  deployment:
    flavor: compose
    mode: docker
```

```bash
curl -fsSL https://signoz.io/foundry.sh | bash
foundryctl cast -f casting.yaml
```

Open `http://localhost:8080`. SigNoz needs Docker with at least 4 GB of memory;
its UI uses port 8080 and OTLP HTTP uses port 4318.

## 2. Enable this application

Install the newly declared dependencies and export the OTLP destination before
starting the API:

```bash
uv sync --dev
export OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318
export OTEL_SERVICE_NAME=iot-anomaly-control
export OTEL_SERVICE_VERSION=demo-2026-07-25
export OTEL_SERVICE_NAMESPACE=water-treatment
export OTEL_DEPLOYMENT_ENVIRONMENT=demo
export OTEL_METRIC_EXPORT_INTERVAL=5000
uv run uvicorn --app-dir src iot_stream.api.main:app --reload
```

For SigNoz Cloud, use the ingestion endpoint and header from **Settings →
Ingestion** instead:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=https://ingest.<region>.signoz.cloud:443
export OTEL_EXPORTER_OTLP_HEADERS=signoz-ingestion-key=<ingestion-key>
export OTEL_SERVICE_NAME=iot-anomaly-control
```

Keep the ingestion key in `.env`, never in source control.

## 3. Verify

Run the telemetry simulator in faulty mode, then open **Services →
`iot-anomaly-control` → Traces**. A single reading creates `sensor.process`;
an anomaly nests detector, retrieval, policy, and `agent.monitor_recovery`
work. The recovery span records the healthy-reading count and whether the
agent automatically closed the software incident after five healthy readings.

## 4. The demo trace to show

In **Services → `iot-anomaly-control` → Traces**, open an anomalous
`sensor.process` trace. It tells one complete operations story:

```text
sensor.process
├── detectors.evaluate                 detector names and anomaly severity
├── knowledge.retrieve                 equipment/sensor filter and top WT-INC ID
├── policy.evaluate                    decision and confidence
├── agent.explain                      Mistral or deterministic fallback
└── agent.monitor_recovery             watching → stabilizing → resolved
```

The parent trace records `anomaly.detected` and `knowledge.scenario_matched`
events, plus the selected incident ID and final policy decision. Filter for
`knowledge.top_incident_id = WT-INC-003` during the seeded Flash Mixer demo,
or `agent.auto_resolved = true` to show safe automatic closure after recovery.

This is why SigNoz is useful in the project: it makes the causal chain
auditable without exposing raw vibration values, raw prompts, Mistral keys, or
operator repair notes.

## 5. Build the operations dashboard

In SigNoz, create a dashboard named **Water Treatment Agent — Trust & Recovery**.
Set its time range to the last 15 minutes and filter every panel by
`service.name = iot-anomaly-control`.

| Panel | Metric | Aggregation | Group by |
| --- | --- | --- | --- |
| Telemetry throughput | `iot.readings` | rate/sum | `equipment.type` |
| Detector activity | `iot.anomalies` | rate/sum | `detector.name` |
| Knowledge grounding | `knowledge.retrievals` | rate/sum | `knowledge.outcome` |
| Agent assessment latency | `agent.assessment.duration` | p95 | `agent.attempted_mode`, `agent.final_mode` |
| Safe auto-resolution | `agent.auto_resolutions` | cumulative sum | `incident.category` |
| Incident time to recovery | `incident.duration` | p95 | `incident.category` |

The Logs Explorer receives correlated business events: `incident.detected`,
`knowledge.scenario_matched`, `agent.assessment_created`, and
`incident.auto_resolved`. Filter them by `incident_id` to show the entire
operator story without exposing raw measurements or repair notes.

For model-latency diagnosis, group `agent.assessment.duration` by both
`agent.attempted_mode` and `agent.final_mode`. A series with `mistral` attempted
and `deterministic` final means the bounded model call failed or timed out and
the safe fallback answered instead.

Official references: [self-hosted Docker installation](https://signoz.io/docs/install/docker/)
and [Python OpenTelemetry setup](https://signoz.io/docs/instrumentation/opentelemetry-python/).
