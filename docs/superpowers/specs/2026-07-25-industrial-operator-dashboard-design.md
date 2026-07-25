# Industrial Operator Dashboard Design

## Purpose

Give a factory operator immediate situational awareness of an asset's vibration
condition and the action required. The dashboard follows high-performance HMI
conventions: neutral presentation by default, with amber and red reserved for
abnormal conditions.

## Layout

1. **Status strip:** stream connection, active incident count, selected asset,
   and current time.
2. **Fleet panel:** concise asset rows showing state, asset identity, current
   vibration, and open incident count.
3. **Condition trend:** the primary panel. It displays the recent vibration
   trace, calculated rolling baseline, expected operating band, warning and
   alarm limits, and detector-event markers.
4. **Operator action:** the current decision, detector reason codes, retrieved
   precedent evidence, and acknowledgement or resolution controls.
5. **Supporting panels:** policy controls and a time-ordered event log.

## Trend semantics

The graph uses the existing 90-point bounded vibration history. A display-only
rolling baseline and expected band are calculated in the browser. They provide
context and do not replace the detector or policy running in the API.

- Actual vibration: dark neutral trace in normal operation; amber/red only
  when the asset state requires attention.
- Baseline: dashed neutral reference line.
- Expected band: subdued filled region around the baseline.
- Warning and alarm limits: labelled horizontal amber/red lines derived from
  the baseline band, clearly marked as dashboard guidance rather than machine
  protection limits.
- Detector events: small markers aligned to the latest readings.

The chart header states current vibration, baseline, and deviation in the
asset's reported unit. Missing samples produce a visible gap rather than a
fabricated zero.

## Data flow

`GET /api/sensors` supplies the initial selected-sensor trend. The existing SSE
`sensor.updated` event appends live readings. Incident state comes from the
existing incident snapshot and SSE incident events. No new API endpoint is
needed for this visual refinement.

## Failure and accessibility behaviour

The existing stream error is visible in the status strip. When there are fewer
than five valid readings, the graph shows the raw trace and an explicit
"baseline learning" state rather than calculating misleading limits. Trend
labels and state copy communicate meaning without relying on colour alone.

## Verification

- Type-check and production-build the Vite dashboard.
- Confirm normal, watch, critical, missing-data, and baseline-learning states.
- Confirm a live SSE reading extends the selected asset's trend without a full
  page reload.
