# Live API and Operational Dashboard Design

## Scope

Connect the current TCP simulator, detector pipeline, incident aggregation, and decision policy to an operational FastAPI service and React dashboard. Sensor readings stream continuously without persistence. Only bounded runtime sensor state and detected incidents remain in memory.

This slice includes live policy reconfiguration and incident actions. It excludes databases, authentication, Docker, RAG, LLM explanations, and production deployment.

## Architecture

One FastAPI background worker owns the TCP simulator connection and processing state:

```text
TCP simulator
    -> ingestion and validation
    -> per-device detectors
    -> incident aggregation
    -> configurable decision policy
    -> in-memory runtime store
    -> REST snapshots and controls + SSE updates
    -> React operator dashboard
```

Browser clients never connect directly to the simulator. This ensures that multiple dashboards observe the same detector and incident state rather than creating independent processing pipelines.

## Runtime State

The API retains only:

- stream connection status and last error;
- latest reading per sensor;
- a bounded vibration trend per sensor;
- a bounded recent-activity list;
- active and resolved incidents created during the current process lifetime;
- acknowledgement and manual-resolution state;
- the active runtime policy configuration; and
- bounded per-client SSE queues.

Raw readings are not stored. All runtime state resets when the API process restarts.

## Processing Flow

Every valid reading:

1. updates latest sensor state and its bounded chart history;
2. runs through that device's detector set;
3. updates category-safe incidents for emitted anomaly events;
4. evaluates affected incidents through the current decision policy;
5. checks quiet-period resolution on every reading; and
6. publishes typed runtime updates.

Changing policy configuration immediately re-evaluates every open incident. Policy changes do not rewrite historical detector evidence.

## HTTP Routes

### Snapshots

- `GET /api/health`: API and stream connection health.
- `GET /api/sensors`: current fleet snapshot.
- `GET /api/sensors/{device_id}`: one sensor with bounded trend.
- `GET /api/incidents`: runtime incidents, optionally filtered by state/category.
- `GET /api/incidents/{incident_id}`: one incident.
- `GET /api/activity`: bounded recent runtime activity.

### Runtime Policy

- `GET /api/policy`: current detector weights and decision thresholds.
- `PUT /api/policy`: replace the active validated policy configuration and re-evaluate open incidents.

Editable fields are spike weight, drift weight, monitor threshold, recommendation threshold, persistence step, maximum persistence bonus, and minimum data-quality readings.

The update rejects non-finite or negative weights, an all-zero weight set, thresholds outside `[0, 1]`, incorrectly ordered thresholds, negative persistence values, and a data-quality minimum below one. Invalid input returns `422` and leaves the current policy unchanged.

### Incident Actions

- `POST /api/incidents/{incident_id}/acknowledge`: records runtime acknowledgement.
- `POST /api/incidents/{incident_id}/resolve`: records manual operator resolution.

Manual resolution does not suppress future evidence. A later anomaly can open a new incident.

### Server-Sent Events

- `GET /api/stream`: one-way live event stream for dashboard clients.

Event names are:

- `sensor.updated`;
- `detector.triggered`;
- `incident.updated`;
- `incident.resolved`;
- `policy.updated`; and
- `stream.status`.

Each event contains JSON and a monotonically increasing runtime event ID. Clients fetch REST snapshots first, then apply SSE updates.

## Streaming Semantics

Each SSE client receives a bounded queue. Slow clients cannot block TCP ingestion. When a queue fills, replaceable sensor updates may be dropped because the latest REST snapshot remains authoritative. Incident, policy, and connection-state changes are prioritized.

SSE sends periodic comments as keep-alives. Client disconnects cleanly remove their queues. Reconnecting browsers fetch fresh snapshots before resuming live updates.

## Disconnection and Errors

The existing ingestion reconnect loop remains responsible for simulator outages. The runtime store transitions through `connecting`, `connected`, and `reconnecting`, retaining last-known sensor and incident state. The dashboard displays the connection state and last error without clearing the page.

Malformed readings are rejected before runtime-state updates. Background worker failures publish a safe stream-status update and retry. Policy failures remain safe escalations.

CORS permits only the local Vite development origin by default.

## Dashboard

The existing visual layout remains, but all mock arrays and fake diagnosis text are replaced by API data.

- Fleet panel: live state, connection freshness, latest values, and sensor selection.
- Sensor detail: current temperature, humidity, vibration, bounded live trend, and last-seen age.
- Incident assessment: actual category, lifecycle state, decision, confidence, detector evidence, reason codes, peak value, and affected-reading count.
- Policy controls: editable runtime fields with explicit `Apply policy`, validation feedback, and a runtime-only notice.
- Operator actions: functional `Acknowledge` and `Resolve` controls.
- Activity log: real detector, incident, policy, and connection events.
- Connection UI: connected, reconnecting, stale, and API-unavailable states without discarding last-known data.

The dashboard uses REST for initial snapshots and commands, and `EventSource` for live updates. State updates are centralized so an SSE event cannot create duplicate sensors or incidents.

## Dependencies

FastAPI and Uvicorn become explicit Python dependencies. The frontend adds no streaming library because browser-native `EventSource` is sufficient.

## Delivery Order

Routes and working runtime behavior take priority over comprehensive automated tests:

1. implement the runtime store and TCP background worker;
2. implement snapshot, policy, incident-action, and SSE routes;
3. verify routes manually with the producer and command-line clients;
4. replace dashboard mocks with REST and SSE state;
5. implement policy editing and incident actions;
6. pass dashboard lint and production build; and
7. add automated route, runtime-store, dashboard-state, and end-to-end tests last.

Basic input validation is implemented with each route and is not deferred.

## Verification

Manual route verification must demonstrate:

- sensor snapshots changing while the producer runs;
- SSE sensor and incident events arriving continuously;
- a valid policy update changing active runtime configuration;
- an invalid policy update returning `422` without mutation;
- acknowledge and resolve actions changing incident state; and
- reconnecting status when the producer stops.

Final automated checks cover route schemas, policy validation, bounded state, incident actions, SSE formatting, deterministic processing into API state, dashboard state transformations, Python tests, dashboard lint/build, and a localhost producer-to-SSE smoke test.

## Acceptance Criteria

The slice is complete when an operator can start the simulator, API, and dashboard; watch current sensor values and trends update continuously; observe real detector and incident outcomes; reconfigure detector weights and thresholds at runtime; acknowledge or resolve incidents; and see connection failures recover without any raw-reading database.
