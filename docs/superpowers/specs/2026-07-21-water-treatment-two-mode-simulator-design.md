# Water-Treatment Two-Mode Simulator Design

**Date:** 2026-07-21
**Status:** Approved for implementation review

## Objective

Replace operator-managed fault scenarios with a coherent six-asset water-treatment fleet and two producer modes:

- `normal`: every asset emits healthy telemetry.
- `faulty`: the simulator autonomously schedules realistic, transient equipment and transport faults.

The simulator emits telemetry and delivery behavior only. It must not create detector events or dashboard incidents directly. The existing consumer, detectors, incident layer, API, and dashboard remain responsible for interpreting the stream.

## Fleet Model

The simulator owns one explicit fleet catalog. Each record contains the stable sensor identifier, plant asset tag, display name, equipment type, and plant area.

| Sensor ID | Asset tag | Display name | Equipment type | Area |
| --- | --- | --- | --- | --- |
| `sensor-1` | `P-101` | Raw Water Intake Pump | `centrifugal_pump` | Intake Station |
| `sensor-2` | `B-201` | Aeration Blower | `aeration_blower` | Biological Treatment |
| `sensor-3` | `M-301` | Flash Mixer | `flash_mixer` | Coagulation Basin |
| `sensor-4` | `C-401` | Sludge Dewatering Centrifuge | `decanter_centrifuge` | Solids Handling |
| `sensor-5` | `P-501` | Chemical Dosing Pump | `metering_pump` | Chemical Room |
| `sensor-6` | `SC-601` | Sludge Screw Conveyor | `screw_conveyor` | Dewatering Area |

`device_id` remains the stable stream identity to avoid breaking detector state and API routes. The asset tag, display name, equipment type, and area are emitted as metadata so downstream layers do not maintain a second hard-coded equipment-name mapping.

The default and supported fleet size for this milestone is six. Any existing device-count option may select a leading subset for development, but must not generate unnamed assets beyond the catalog.

## Producer Interface

The primary producer interface becomes:

```bash
uv run main.py produce --mode normal --seed 42 --interval 0.1
uv run main.py produce --mode faulty --seed 42 --interval 0.1
```

`--mode` accepts only `normal` and `faulty`. The default is `normal` so an omitted mode is safe and unsurprising. `--seed` controls all pseudo-random decisions, including noise, asset selection, fault selection, timing, duration, and severity, so test and demo runs are reproducible.

Named scenarios such as `known_fault`, `novel_fault`, and `data_quality` are removed from the operator-facing producer contract. Existing waveform helpers may remain as internal implementation primitives where useful; they are not selectable operating modes.

## Normal Mode

Normal mode emits plausible baseline temperature, humidity, and vibration values with ordinary measurement noise. It never intentionally injects an equipment fault, missing reading, duplicate event, or sequence rewind.

All six assets continue emitting indefinitely at the configured interval. Their baseline values may differ by equipment type, but normal variation must remain below the current detector thresholds during a deterministic smoke run.

## Faulty Mode Scheduler

Faulty mode uses a seeded scheduler rather than assigning one permanent scenario to each sensor.

1. The plant starts with a healthy warm-up period so detectors can establish baselines.
2. After a randomized quiet interval, the scheduler selects an asset that has no active injected fault.
3. It selects a fault compatible with that equipment, plus seeded severity and duration values within bounded ranges.
4. The selected fault modifies that asset's telemetry or transport behavior while all unaffected assets continue normally.
5. When the duration expires, the asset recovers to its normal baseline. Recovery is bounded and must not permanently shift the generated baseline.
6. A cooldown follows before another fault is scheduled.

The scheduler may allow faults on different assets to overlap after the first implementation proves stable, but it must never stack two injected faults on the same asset. The initial implementation should limit concurrency to one active injected fault at a time; this gives operators an understandable stream and keeps detector tuning attributable. The scheduler structure must make a later increase in concurrency straightforward.

Timing is expressed in emitted readings rather than wall-clock seconds, preserving the same seeded behavior when `--interval` changes. Initial bounded ranges are:

- warm-up: 60–100 readings per asset;
- healthy gap: 40–100 scheduler ticks;
- active fault: 30–90 readings for the selected asset;
- recovery: immediate for transient transport faults and a short ramp for drifting physical values.

These values are implementation defaults, not dashboard-configurable detector policy.

## Equipment-Aware Fault Catalog

Physical faults are selected only where the telemetry signature is credible:

| Equipment | Candidate signatures |
| --- | --- |
| Raw Water Intake Pump | cavitation vibration bursts; bearing temperature rise |
| Aeration Blower | sustained overheating; gradual vibration drift |
| Flash Mixer | shaft imbalance; intermittent vibration instability |
| Sludge Dewatering Centrifuge | severe rotor imbalance; bearing temperature rise |
| Chemical Dosing Pump | intermittent low-vibration operation; vibration bursts |
| Sludge Screw Conveyor | mechanical overload; gradual bearing degradation |

Transport/data-quality faults can affect any asset:

- duplicate event/replay;
- sequence rewind or repetition;
- missing reading where the current protocol can represent it without fabricating a downstream incident.

Each injected behavior must change raw readings or event delivery in a way the current detector can independently recognize. Fault compatibility and generated amplitude should be centralized in the simulator rather than scattered through CLI branches.

## Stream Contract

The reading contract adds the following metadata:

- `asset_id`
- `equipment_name`
- `area`

The existing `device_id` and `equipment_type` fields remain. New metadata is required for simulator-generated readings and is carried unchanged through the TCP consumer, runtime state, API responses, and SSE updates.

For compatibility with hand-authored or older messages, downstream schema parsing should use a safe fallback derived from `device_id` or `equipment_type` when the new display fields are absent. The live simulator itself always emits the full contract.

## Consumer and Detection Boundary

The TCP consumer continues to decode newline-delimited readings and pass them to the stream processor. Detectors remain unaware of producer mode and do not trust producer fault labels when deciding whether to emit an event.

Detector behavior remains policy-driven:

- physical telemetry is evaluated by spike, drift, and threshold logic;
- event identifiers and sequence numbers are evaluated by data-quality logic;
- only detector output enters incident correlation and the dashboard alert path.

Ground-truth fault metadata may remain on generated readings for tests and evaluation, but the production detection path must not branch on it.

## API and Dashboard

The API uses emitted fleet metadata for sensor names and locations instead of its current four-item label mapping. Its health/runtime response exposes a configured fleet size of six so the UI can render accurate coverage before every sensor has reported.

The dashboard must:

- show six assets using their plant display names and asset tags;
- show the plant area for the selected asset;
- calculate fleet coverage against six;
- continue streaming healthy readings while a different asset is faulty;
- surface incidents only when the detector emits them;
- show recovery through returning telemetry and incident lifecycle state;
- preserve the existing runtime detector-policy controls.

No telemetry history database is introduced. The dashboard remains a live runtime view, retaining only the bounded in-memory state already required for current readings, activity, and detected incidents.

## Compatibility and Documentation

Documentation and examples are updated from scenario-based commands to the two-mode interface. References to a four-sensor fleet are changed to six where they describe the simulator or dashboard contract.

Because this is a deliberate CLI simplification, unsupported scenario values should fail with a clear message directing users to `--mode normal` or `--mode faulty`; they should not silently map to a mode.

## Verification

Implementation verification covers:

1. Fleet catalog tests: six unique sensors, asset tags, names, equipment types, and areas.
2. Normal-mode tests: a seeded bounded run emits all six sensors without intentional fault metadata or detector incidents after warm-up tolerances are accounted for.
3. Faulty-mode scheduler tests: seeded runs select compatible assets and faults, activate them transiently, recover, and leave unaffected sensors healthy.
4. Reproducibility tests: identical seeds produce the same scheduling decisions and reading sequence.
5. Contract tests: new metadata survives simulator serialization, TCP parsing, runtime projection, API responses, and SSE payloads.
6. Detection-boundary tests: ground-truth labels alone do not create incidents; anomalous telemetry or delivery behavior does.
7. Dashboard checks: six-asset coverage, display metadata, live recovery, and existing policy controls build and lint successfully.
8. End-to-end smoke test: start consumer/API, run `faulty`, observe all six streams and at least one detector-created incident followed by recovery.

## Out of Scope

- user-authored scenario files;
- a dashboard control for producer mode;
- persistent telemetry storage;
- predictive maintenance or remaining-useful-life modeling;
- simultaneous multi-fault tuning beyond the scheduler seam;
- modeling hydraulic process dependencies between assets.

