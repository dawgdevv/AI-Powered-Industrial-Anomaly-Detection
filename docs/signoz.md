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
`iot-anomaly-control` → Traces**. A single reading creates `sensor.process`.
When the detector finds an equipment condition, the immediate safety decision
is recorded first; semantic retrieval and the optional Mistral refinement run
in the background so an embedding or model request cannot pause ingestion.
The recovery span records the healthy-reading count, the stable-normal window,
and whether the agent automatically closed the software incident only after
retrieval finished and five healthy readings were sustained for the configured
observation window.

## 4. The demo trace to show

In **Services → `iot-anomaly-control` → Traces**, open an anomalous
`sensor.process` trace. It tells one complete operations story:

```text
sensor.process
├── detectors.evaluate                 detector names and anomaly severity
├── incident.evaluate
│   └── policy.evaluate                immediate detector-only safe decision
├── knowledge.enrich_incident          asynchronous evidence enrichment
│   ├── knowledge.retrieve             filtered Chroma search and top WT-INC ID
│   └── policy.re_evaluate             decision updated with retrieved evidence
├── agent.explain                      deterministic assessment, then optional Mistral refinement
└── agent.monitor_recovery             watching → stabilizing → resolved
```

`knowledge.enrich_incident` is deliberately asynchronous, so it can extend
beyond the short `sensor.process` span while retaining the same trace context.
The trace records `anomaly.detected` and `knowledge.scenario_matched` events,
plus the selected incident ID and final policy decision. Filter for
`knowledge.top_incident_id = WT-INC-003` during the seeded Flash Mixer demo,
or `agent.auto_resolved = true` to show safe automatic closure after recovery.

This is why SigNoz is useful in the project: it makes the causal chain
auditable without exposing raw vibration values, raw prompts, Mistral keys, or
operator repair notes.

## 5. Build the operations dashboard

In SigNoz, create a dashboard named **Water Treatment Agent — Trust & Recovery**.
Set its time range to the last 15 minutes and filter every panel by
`service.name = iot-anomaly-control`.

| Panel | Metric | Query Builder setup | Group by |
| --- | --- | --- | --- |
| Telemetry throughput | `iot.readings` | **Rate** within series → **Sum** across series | `equipment.type` |
| Detector activity | `iot.anomalies` | **Increase** within series → **Sum** across series | `detector.name` |
| Safety-policy decisions | `policy.decisions` | **Increase** within series → **Sum** across series | `policy.decision` |
| Knowledge grounding | `knowledge.retrievals` | **Increase** within series → **Sum** across series | `knowledge.outcome` |
| Agent assessment latency | `agent.assessment.duration` | **P95** within series | `agent.attempted_mode`, `agent.final_mode` |
| Safe auto-resolution | `agent.auto_resolutions` | **Increase** within series → **Sum** across series → Number panel: **Sum of values in timeframe** | no grouping for one total; optionally `incident.category` |
| Incident time to recovery | `incident.duration` | **P95** within series | `incident.category` |

For every panel, add the resource filter `service.name = iot-anomaly-control`.
For the two histogram metrics, SigNoz may show the stored metric name with a
`.bucket` suffix; select it and keep the P95 aggregation. Do not use **Rate**
for `agent.auto_resolutions`: it produces a rate, not the demo's total count,
and a Number visualization can render that empty reduction as `NaN`.

The Logs Explorer receives correlated business events: `incident.detected`,
`knowledge.scenario_matched`, `agent.assessment_created`, and
`incident.auto_resolved`. Filter them by `incident_id` to show the entire
operator story without exposing raw measurements or repair notes.

For model-latency diagnosis, group `agent.assessment.duration` by both
`agent.attempted_mode` and `agent.final_mode`. A series with `mistral` attempted
and `deterministic` final means the bounded model call failed or timed out and
the safe fallback answered instead.

## 6. Saved investigation views

Create these two saved views after the dashboard is receiving data:

1. **Agentic incident trace** — Trace Explorer filter
   `service.name = iot-anomaly-control`, span name `sensor.process`. Open a
   trace with `incident.id` and expand `knowledge.enrich_incident`. This makes
   the detector → evidence → policy → agent sequence visible.
2. **Water-treatment incident events** — Logs Explorer filter
   `service.name = iot-anomaly-control` and search for one of
   `incident.detected`, `knowledge.scenario_matched`,
   `agent.assessment_created`, or `incident.auto_resolved`. Add `incident_id`
   as a displayed field to follow one operational story.

The application intentionally sends only incident metadata, decision state,
and timing to SigNoz; raw vibration values, prompts, repair notes, and secrets
stay out of observability data.

## 7. Open the exact incident trace from the operator dashboard

When an anomaly first opens an incident, the API stores the W3C trace ID from
that reading's `sensor.process` root span with the incident in SQLite. The
Flow Warden console exposes **Open trace in SigNoz** for both active and last
resolved incidents. It opens:

```text
http://localhost:8080/trace/<incident-trace-id>
```

The dashboard defaults to local SigNoz. For a remote SigNoz UI, copy
`dashboard/.env.example` to `dashboard/.env` and set:

```bash
VITE_SIGNOZ_URL=https://your-signoz-ui.example
```

Restart the Vite server after changing this variable. Incidents created while
OTLP is disabled have no trace ID, and the dashboard explains that instead of
showing a broken link.

## 8. Alerts to configure

Create these in **Alerts → New Alert** with the same
`service.name = iot-anomaly-control` filter. They are operational guardrails,
not machine-control actions.

| Alert | Query | Suggested condition | Why it matters |
| --- | --- | --- | --- |
| Telemetry stopped | `iot.readings`, Rate then Sum | below `0.1` for 2 minutes | detects an unavailable producer, API, or collector path |
| Safety escalation | `policy.decisions`, filter `policy.decision = ESCALATE`, Increase then Sum | at least `1` in 5 minutes | sends an operator attention signal when runtime policy will not recommend a routine response |
| Duplicate-event burst | `iot.anomalies`, filter `detector.name = duplicate_event`, Increase then Sum | at least `3` in 5 minutes | surfaces data-quality issues before equipment conclusions are trusted |
| Mistral fallback / agent error | `agent.assessments`, filter `agent.attempted_mode = mistral` and `agent.final_mode = deterministic`, Increase then Sum | at least `1` in 5 minutes | proves the deterministic safety fallback is being used and prompts provider investigation |
| Agent abstention | `agent.assessments`, filter `agent.outcome = abstained`, Increase then Sum | at least `1` in 5 minutes | tells the operator the agent lacks enough safe evidence to give a confident recommendation |
| Slow Mistral assessment | `agent.assessment.duration`, filter `agent.attempted_mode = mistral`, P95 | above `6 s` for 5 minutes | warns before the bounded explanation path becomes unhelpful |
| Slow recovery | `incident.duration`, P95 | above `90 s` for 10 minutes | flags incidents that are not stabilizing quickly enough |

Send telemetry, policy, duplicate, and abstention alerts to the operator
channel; send Mistral fallback and latency alerts to the engineering channel.
Keep alerts in **notify-only** mode: SigNoz must not issue machine commands.

## 9. What remains after this configuration

The application instrumentation, dashboard metrics, logs, trace deep links,
and automated OTLP-export verification are ready. Two work items remain
outside this runbook:

- Create and save the alert rules in your local SigNoz workspace.
- Optionally configure a SigNoz MCP connector for assistant-led investigation.

There is no SigNoz MCP connector configured for this workspace, so incident
investigation currently uses the SigNoz UI directly.

Official references: [self-hosted Docker installation](https://signoz.io/docs/install/docker/)
and [Python OpenTelemetry setup](https://signoz.io/docs/instrumentation/opentelemetry-python/).
