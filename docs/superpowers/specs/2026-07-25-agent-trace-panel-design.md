# Agent Trace Panel Design

## Purpose

Replace the dashboard's current Agent Guidance panel with one operator-readable trace of how the system reached, maintains, and closes an equipment-condition incident.

## Scope

The panel consumes the existing incident snapshot delivered over SSE. It does not add polling, a new endpoint, model tools, or an automatic physical control action.

## Layout

The panel is a chronological six-stage trace:

1. **Live observation** — latest vibration and temperature, plus equipment identity.
2. **Condition detected** — active detector names and the incident decision.
3. **Water-treatment scenario** — the top retrieved scenario ID, source kind, and likely fault.
4. **Assessment** — assessment title, explanation, and source provenance: Mistral when `model` is present and `model_fallback` is false; otherwise safe deterministic assessment.
5. **Recovery watch** — `watching live telemetry` while active; `software incident returned to normal` when resolved. Internal healthy-reading counters are never rendered.
6. **Operator diagnosis** — an initially collapsed form for outcome and repair notes. A confirmed diagnosis saves through the existing review endpoint and can enrich Chroma.

## Data contract

Existing fields are sufficient: incident state, detector list, decision, retrieval evidence, agent assessment, review, and the selected sensor's live values. The component receives the selected `Sensor` in addition to the existing `Incident`.

## State and failure behavior

- Incoming SSE incident snapshots replace trace content immediately.
- The panel labels deterministic fallback honestly; it never suggests a model produced text when it did not.
- If review saving fails, keep the diagnosis workspace open and render the API error beside the submit action.
- Once a review is saved, render the outcome and saved notes as the final trace stage.

## Accessibility and motion

- Retain semantic buttons and labels.
- Add `aria-live="polite"` to the changing assessment/recovery area.
- Use visible keyboard focus states.
- Continue honoring reduced-motion preferences.

## Acceptance criteria

- Current Agent Guidance is completely replaced by Agent Trace.
- Trace is readable without knowing the model internals.
- It distinguishes Mistral from deterministic fallback.
- It makes water-treatment scenario retrieval visible.
- It uses the existing `/api/stream` and `/api/incidents/{id}/review` contracts.
- Dashboard typecheck/build succeeds.
