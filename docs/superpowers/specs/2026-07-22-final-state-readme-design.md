# Final-State README Design

**Date:** 2026-07-22
**Status:** Approved for written review

## Objective

Rewrite the repository README around the proposed finished product while preserving an explicit and honest boundary between the final vision and the capabilities currently implemented.

The README should help a new developer, reviewer, or hackathon judge understand three things quickly:

1. what the finished industrial anomaly-control system will do;
2. why its evidence, abstention, and observability model matters;
3. how far the current repository has progressed toward that outcome.

## Narrative Structure

The README will use a vision-first structure:

1. Product promise and industrial safety problem.
2. Final end-to-end architecture.
3. Final product behavior through three outcome paths.
4. Water-treatment fleet and simulator modes.
5. Evidence, decision ownership, and abstention rules.
6. Final operator dashboard and observability experience.
7. Current runnable quick start and API surface.
8. Current progress versus remaining work.
9. Final definition of done and verification commands.

The finished system is the primary narrative. The progress section remains visible and uses precise status labels so planned work is not represented as implemented.

## Proposed Final Architecture

The final flow is:

```text
Water-treatment simulator
    → validated stream ingestion
    → deterministic and statistical detectors
    → incident aggregation
    → filtered historical-incident retrieval
    → application-owned confidence and abstention policy
    → bounded LLM explanation
    → maintenance recommendation or human-review escalation
    → FastAPI, operator dashboard, and OpenTelemetry/SigNoz
```

The README will make ownership explicit:

- detectors identify observable signal and transport problems;
- retrieval supplies relevant verified precedents;
- application policy owns the final decision;
- the LLM explains an approved decision and cannot override policy;
- SigNoz makes the evidence path inspectable;
- operators acknowledge, review, and resolve outcomes.

## Final Outcome Paths

The finished product will be explained through three outcomes rather than manually managed simulator scenarios:

### Verified precedent

A transient physical fault is detected, correlated into an equipment incident, matched to a strong verified historical precedent, and converted into a bounded maintenance recommendation with cited evidence.

### Weak or novel evidence

An anomaly is detected but retrieval is empty, weak, ambiguous, or unverified. The application abstains, records reason codes, and creates a human-review escalation rather than allowing the model to guess.

### Data-quality failure

Missing readings, duplicate events, sequence failures, or stale data create a data-quality alert. They do not trigger a mechanical diagnosis or equipment recommendation.

## Final Dashboard and Observability Scope

The final dashboard description will include:

- live six-asset fleet state and sensor trends;
- detector evidence and incident lifecycle;
- retrieved historical precedents and similarity evidence;
- confidence components, final decision, and abstention reasons;
- bounded AI explanation and recommended action;
- human-review queue, acknowledgement, outcome, and resolution;
- a direct link from each investigation to its SigNoz trace.

The observability section will describe one investigation trace spanning ingestion, validation, detection, aggregation, retrieval, confidence calculation, model invocation, policy enforcement, and dispatch. It will also describe operational and AI-decision metrics, structured logs, and safety alerts.

## Current-State Boundary

The README must not imply that proposed capabilities already exist. A dated progress table will distinguish:

- **Complete:** six-asset simulator, normal/faulty modes, transient recovery, TCP ingestion, validation, deterministic detectors, incident aggregation and lifecycle, current detector-agreement policy, REST/SSE API, live dashboard, and runtime policy controls.
- **Next milestone:** structured historical incident knowledge base, filtered retrieval, and retrieval-aware confidence integration.
- **Planned:** bounded LLM explanation, full human-review persistence, OpenTelemetry/SigNoz, deployment packaging, and clean-clone demo assets.

Statements about test counts and successful builds will appear only in the current progress or verification section.

## Quick Start and API Accuracy

The README will retain commands that work against the repository today:

- `uv run main.py produce --mode normal|faulty`;
- `uv run uvicorn --app-dir src iot_stream.api.main:app --reload`;
- `bun run dev`, `bun run lint`, and `bun run build`;
- `uv run python -m unittest discover -v`.

Current REST and SSE routes will remain documented. Proposed retrieval, explanation, review, and trace fields will be described as the final contract, not listed as live endpoints until implemented.

## Tone and Presentation

The README should be credible, safety-focused, and judge-friendly. It will prefer concrete outcome language over broad AI claims, avoid presenting the LLM as the decision-maker, and keep the distinction between equipment faults and data-quality failures clear.

The final vision should feel cohesive rather than like a list of disconnected future technologies. The six-asset water-treatment plant remains the single demonstration domain.

## Acceptance Criteria

The rewrite is complete when:

1. the final product architecture and value are understandable before the progress section;
2. RAG, LLM, observability, and human review are described as parts of the proposed final system;
3. current and planned capabilities are unmistakably differentiated;
4. the three safe outcome paths are documented;
5. current startup, API, and verification instructions remain accurate;
6. no obsolete four-sensor, named-scenario, mock-dashboard, or LLM-owned-decision claims remain;
7. the README ends with a measurable final definition of done.

