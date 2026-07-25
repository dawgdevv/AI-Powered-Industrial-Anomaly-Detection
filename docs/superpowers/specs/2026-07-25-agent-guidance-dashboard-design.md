# Agent Guidance Dashboard Design

## Goal

Replace the static incident form and visible recovery counter with a concise,
live agent-guidance experience for water-treatment operators. The agent owns
monitoring and automatic recovery. The operator owns the diagnosis and repair
record.

## Interaction model

The incident panel has three state-aware modes:

1. **Active incident — Guide my inspection**
   - Shows the agent’s current fault hypothesis, the retrieved water-treatment
     scenario, and the immediate inspection focus.
   - One CTA opens the guided diagnosis workspace.

2. **Monitoring recovery — Capture diagnosis**
   - Explains that normal readings are being monitored and the software state
     will return to normal automatically.
   - Does not show a numeric healthy-reading counter.
   - Keeps the diagnosis CTA available for maintenance findings.

3. **Auto-resolved — Save final diagnosis**
   - States that the agent returned the software incident to normal after
     stable readings.
   - Makes final diagnosis capture the primary action.

## Guided diagnosis workspace

The workspace is hidden until the CTA is selected. It contains only the fields
needed to create useful local knowledge:

- diagnosis outcome: confirmed fault, false alarm, or different cause;
- maintenance finding and repair completed;
- a short agent-provided prompt based on the current incident.

Submitting persists the report through the existing review endpoint and, for a
confirmed fault, enriches the local knowledge collection.

## Visual and behavioral rules

- Preserve the dark low-glare control-room palette and compact technical type.
- Use a state label and short agent status line instead of a progress counter.
- Animate only the agent-status change and guided workspace reveal; honor
  `prefers-reduced-motion`.
- Do not change incident state from the dashboard; the agent/runtime remains
  the sole owner of automatic recovery and resolution.
- Update the panel from existing SSE incident events, including agent
  assessment updates and auto-resolution.

## Testing

- Dashboard build must pass.
- Existing API contract remains unchanged: diagnosis still uses
  `POST /api/incidents/{incident_id}/review`.
- Agent state display must work for active, monitoring, and resolved incidents
  without relying on the removed healthy-reading fields.
