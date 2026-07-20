# IoT Streaming Agentic RAG

Real-time anomaly detection for industrial sensors, built on an agent that
knows when to explain and when to admit it doesn't know.

## The problem

Factory sensor data (vibration, temperature, humidity) already triggers
threshold alarms today. Those alarms are dumb: they fire on a fixed number,
give no context, and cause **alarm fatigue** — operators start ignoring
alerts because most are noise, not real faults. This is a documented root
cause in real industrial incidents (Texas City, Deepwater Horizon).

## What this system does

1. **Simulates** a fleet of IoT sensors streaming live data over TCP,
   each with a distinct realistic fault mode (spike, drift, dropout,
   duplicate reads) — not just generic noise.
2. **Detects** anomalies in real time from the live stream (rolling
   stats + Isolation Forest).
3. **Reasons** about detected anomalies using an LLM agent that retrieves
   similar past incidents from a small knowledge base (RAG).
4. **Decides**: if confident, it explains the likely cause in plain
   English. If not confident, it escalates to a human instead of guessing.
5. **Traces** every decision (latency, tokens, confidence, outcome) for
   observability.

## Why the abstention matters

A wrong diagnosis on a factory floor isn't a bad chatbot reply — it's a
safety or liability event. Most AI demos always produce an answer. This
one is built to say "I don't know" on purpose when the evidence doesn't
support a confident call.

## Worked example

**2am, Sensor-4 (pump vibration) starts climbing** from a 0.2 baseline to
2.8 — a 14x jump.

- **Without this system**: it's a line in a log. Nobody notices until the
  pump fails days later, causing unplanned downtime.
- **With this system**: the stream processor flags the statistical
  anomaly within seconds. The agent searches its knowledge base and finds
  a near-identical signature from 3 months ago, tagged "bearing wear,
  replaced before failure." Confidence is high, so it pages an engineer:
  _"Sensor-4 shows the signature of early bearing wear based on incident
  #0092. Recommend inspection within 48 hours."_

**Contrast case — Sensor-2 shows something novel.** No matching precedent
in the knowledge base. Instead of guessing, the agent responds: _"No
matching precedent, confidence below threshold — escalating to human
review."_ That's the differentiator: knowing when not to answer.

## Architecture

```
IoT simulator → Stream processor → Agentic RAG layer → Observability → API + dashboard
```

- **Simulator**: standalone Python service, broadcasts JSON over TCP
- **Stream processor**: rolling z-score + Isolation Forest
- **Agentic RAG**: vector store (Chroma) + LLM reasoning + abstention rule
- **Observability**: OpenTelemetry traces → Signoz
- **API**: FastAPI, exposes live status + incident history

## Status

- [x] IoT simulator with 4 fault modes (anomaly, drift, MCAR, duplicate)
- [x] TCP broadcast, verified end-to-end with a live consumer
- [ ] Stream processor (anomaly detection over the live feed)
- [ ] Knowledge base + RAG retrieval
- [ ] Agent with confidence-based abstention
- [ ] Observability (Signoz/OpenTelemetry)
- [ ] FastAPI + dashboard
