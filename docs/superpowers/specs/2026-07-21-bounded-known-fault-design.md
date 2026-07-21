# Bounded Known-Fault Demo Design

## Scope

Correct the `known_fault` demo so it represents one believable pump incident instead of applying an unbounded fault to the whole fleet. Reduce consumer noise by making incident transitions the default output while preserving raw detector events as an explicit debugging mode.

This correction does not add retrieval, an LLM, observability infrastructure, an API, or dashboard integration.

## Fleet Behavior

Only `sensor-1`, a centrifugal pump with a vibration sensor measured in `mm/s`, receives the known-fault waveform. Sensors 2–4 continue emitting stable, seeded normal telemetry for the entire run. Their readings retain independent random-walk variation but cannot inherit the named equipment fault.

Named scenarios therefore select a fleet-level assignment rather than blindly configuring every sensor with the same behavior.

## Bounded Fault Waveform

The `sensor-1` waveform has explicit phases:

1. `BASELINE`: collect sufficient normal history around the configured vibration baseline.
2. `DRIFT`: increase vibration gradually to a configured upper operating bound.
3. `SPIKE`: emit one deliberate high-vibration reading after drift evidence exists.
4. `ELEVATED`: hold a bounded abnormal level briefly without increasing forever.
5. `RECOVERY`: return smoothly to the baseline.
6. `NORMAL`: remain stable indefinitely.

All ordinary drift and elevated values remain within configured realistic bounds. Only the deliberate spike may exceed the upper operating bound, and it is itself capped. Phase boundaries and amplitude constants are named configuration values rather than unexplained inline arithmetic.

The detector must observe both drift and spike evidence during the scenario. The waveform stops adding fault energy after the configured phases, so long-running demos cannot reach impossible values.

## Incident-Focused Consumer

The stream processor gains a small command-line interface:

- `--mode incidents` is the default and consumes the stream through detection, aggregation, and policy.
- `--mode events` preserves the existing raw anomaly-event output.
- `--host` and `--port` configure the producer connection.

Incident mode prints only meaningful changes for an incident. A change is meaningful when the incident is first observed, its decision changes, its confidence crosses the recommendation threshold, or it resolves. Repeated detector evidence that leaves the decision unchanged updates aggregation state without printing another alert.

Expected known-fault output is a concise progression such as `MONITOR`, then `RECOMMEND`, then `RESOLVED`. Output includes incident ID, device, category, decision, confidence, detector names, and reason codes.

## Duplicate Transport Semantics

A replay with both the same `event_id` and the same sequence number emits one `duplicate_event`. It does not also emit `sequence_rewind`.

A lower sequence number still emits `sequence_rewind`. Reuse of the same sequence number with a different event ID also emits `sequence_rewind`, because it represents a distinct sequence-integrity problem rather than a byte-for-byte replay.

## Resolution

The processor evaluates quiet-period resolution on every valid reading. When sensor-1 has returned to normal and no new anomaly evidence arrives for the configured quiet period, its incident transitions to `RESOLVED` and that transition is printed once.

For a fast demo, phase and quiet-period timing are based on reading timestamps and configured windows, not wall-clock sleeps. The default `--interval 0.1` scenario reaches recommendation and resolution within a short interactive run.

## Error Handling

- Unknown CLI modes are rejected by argument parsing.
- Connection failures retain exponential-backoff reconnect behavior.
- Invalid scenario configuration fails before the producer starts.
- Policy failures remain safe escalations.
- Normal sensors cannot contribute evidence to sensor-1's incident because detector and aggregation state remain per-device.

## Testing

Tests verify:

- only sensor-1 receives the known fault;
- sensors 2–4 remain inside their configured normal range;
- sensor-1 values remain bounded through a long run;
- the waveform produces drift, then one spike, then recovery;
- detector agreement reaches `RECOMMEND`;
- recovery and the quiet period reach `RESOLVED`;
- replayed messages produce one duplicate alert rather than two transport alerts;
- lower or independently reused sequences still produce sequence-integrity alerts;
- incident output suppresses unchanged repeated decisions; and
- raw event mode remains available.

## Acceptance Criteria

The correction is complete when a long-running `known_fault` producer keeps sensors 2–4 normal, sensor-1 remains bounded, the default consumer shows one concise incident progression through recommendation and resolution, raw events remain opt-in, and all Python and dashboard checks pass.
