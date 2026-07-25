# Demo faulty-mode cadence

## Goal

Give the demo a readable healthy baseline before any anomaly, then show a
knowledge-grounded equipment incident without data-quality noise obscuring the
first retrieval and agent-recovery story.

## Schedule

- Seconds `0–60`: all six assets emit normal telemetry. No equipment or
  data-quality fault may start.
- Seconds `60–100`: one seeded, shuffled, knowledge-backed equipment scenario
  runs. Its asset and fault family are resolved from the indexed
  water-treatment incident catalog.
- Seconds `100–120`: the asset returns to normal. The runtime has ample
  healthy readings to demonstrate its five-reading auto-resolution rule.
- Every 60 seconds after the first start: another equipment scenario begins;
  the shuffled deck still covers each of the six scenarios before repetition.
- Data-quality faults remain eight seconds long and recur every 30 seconds,
  but their first start moves to second `180`. This leaves the baseline and the
  first two equipment demonstrations uncluttered.

## Boundaries

The fault waveform, scenario mapping, seed behavior, detector rules,
retrieval filters, and API behavior do not change. The mock remains the only
component that knows the planned schedule; runtime decisions continue to use
telemetry and retrieved evidence only.

## Verification

The faulty-mode test will assert the 60-second clean baseline, first equipment
start at second 60, second start at second 120, and first data-quality start at
second 180. Existing source-catalog validation continues to reject an asset
whose equipment type does not match its mapped knowledge incident.
