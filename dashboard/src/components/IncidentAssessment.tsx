import { useEffect, useState } from 'react'
import type { Incident, Sensor } from '../types/dashboard'

type Outcome = 'confirmed_fault' | 'false_alarm' | 'different_cause'
type Props = { incident?: Incident; resolvedIncident?: Incident; sensor?: Sensor; onReview: (id: string, outcome: Outcome, notes: string) => Promise<void> }
const signozBaseUrl = (import.meta.env.VITE_SIGNOZ_URL || 'http://localhost:8080').replace(/\/+$/, '')

function display(value: string | null | undefined) {
  return value ? value.replaceAll('_', ' ') : 'Not available'
}

function WardenMark({ active }: { active: boolean }) {
  return <span className={`warden-mark ${active ? 'awake' : ''}`} aria-hidden="true"><svg viewBox="0 0 48 48"><path d="M24 5 39 13v22L24 43 9 35V13L24 5Z" /><path d="M15 24h18M24 15v18" /><circle cx="24" cy="24" r="5" /></svg></span>
}

function TraceLink({ incident }: { incident: Incident }) {
  if (!incident.trace_id) return <small className="trace-link-unavailable">Trace link appears when OTLP export is enabled.</small>
  return <a className="trace-link" href={`${signozBaseUrl}/trace/${incident.trace_id}`} target="_blank" rel="noreferrer"><span>OPEN TRACE IN SIGNOZ</span><code>{incident.trace_id.slice(0, 8)}…{incident.trace_id.slice(-6)}</code><em>↗</em></a>
}

function recoveryMessage(incident: Incident) {
  if (incident.recovery_state === 'awaiting_knowledge') return 'Normal readings are holding. Flow Warden is waiting for the knowledge trace to finish before clearing this investigation.'
  if (incident.recovery_state === 'observing_normal') return `Normal readings are consistent. Keeping the evidence visible for ${incident.recovery_stability_seconds ?? 8} seconds before closure.`
  if (incident.agent_active) return 'Flow Warden is monitoring for stable normal readings, then will retain the completed evidence briefly before closure.'
  return 'Recovery cannot be evaluated until the live stream resumes.'
}

function DiagnosisForm({ incident, onReview }: { incident: Incident; onReview: Props['onReview'] }) {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [outcome, setOutcome] = useState<Outcome>('confirmed_fault')
  const [notes, setNotes] = useState('')
  const submit = async () => {
    if (notes.trim().length < 3) return
    setError(null); setPending(true)
    try { await onReview(incident.incident_id, outcome, notes.trim()) }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not save the diagnosis. Try again.') }
    finally { setPending(false) }
  }
  return <section className="diagnosis-workspace" id="operator-diagnosis"><div><span>OPERATOR DIAGNOSIS</span><b>What was the final finding and repair?</b></div><label><span>OUTCOME</span><select name="outcome" value={outcome} onChange={(event) => setOutcome(event.target.value as Outcome)}><option value="confirmed_fault">Confirmed fault and solution</option><option value="false_alarm">False alarm</option><option value="different_cause">Different cause</option></select></label><label><span>FINDING AND REPAIR</span><textarea name="finding-and-repair" value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Describe the cause, repair, and verification completed…" /></label>{error ? <p className="diagnosis-error" role="alert">{error}</p> : null}<button className="agent-submit" type="button" disabled={pending || notes.trim().length < 3} onClick={submit}>{pending ? 'Saving diagnosis…' : 'Save diagnosis to agent memory'}</button></section>
}

export function IncidentAssessment({ incident, resolvedIncident, sensor, onReview }: Props) {
  const [open, setOpen] = useState(false)
  useEffect(() => setOpen(false), [incident?.incident_id, resolvedIncident?.incident_id])

  if (!incident) return <aside className="assessment-panel warden-console standby"><div className="warden-heading"><WardenMark active={false} /><div><p className="eyebrow">FLOW WARDEN / AGENT CONSOLE</p><h2>Standing watch</h2><span>Monitoring every live asset</span></div><i className="warden-state">STANDBY</i></div><div className="warden-standby"><b>No active equipment investigation</b><p>Flow Warden will wake when detector evidence opens an equipment incident. Resolved scenarios are cleared from this console so the next investigation starts cleanly.</p></div>{resolvedIncident ? <section className="resolved-handoff"><span>LAST WORKFLOW CLOSED</span><b>{resolvedIncident.incident_id} returned to normal</b><p>The active knowledge scenario has been cleared. Record the maintenance finding from this completed workflow if needed.</p><TraceLink incident={resolvedIncident} />{resolvedIncident.review ? <small>Operator diagnosis saved · {display(resolvedIncident.review.outcome)}</small> : <button type="button" className="agent-primary" onClick={() => setOpen((value) => !value)}>{open ? 'Close report workspace' : 'Record completed finding'}<em>→</em></button>}</section> : null}{open && resolvedIncident && !resolvedIncident.review ? <DiagnosisForm incident={resolvedIncident} onReview={onReview} /> : null}</aside>

  const assessment = incident.agent_assessment
  const precedent = incident.retrieval_evidence?.[0]
  const modelLabel = assessment?.model && !assessment.model_fallback ? assessment.model : 'Safe deterministic assessment'
  return <aside className="assessment-panel warden-console active-investigation">
    <div className="warden-heading"><WardenMark active /><div><p className="eyebrow">FLOW WARDEN / ACTIVE INVESTIGATION</p><h2>{incident.incident_id}</h2><span>{sensor?.equipment_name ?? incident.device_id}</span></div><i className="warden-state">AWAKE</i></div>
    <p className="warden-intro">Flow Warden is tracing the signal, checking the water-treatment knowledge base, and watching recovery. It does not control plant equipment.</p>
    <TraceLink incident={incident} />
    <ol className="trace-list">
      <li className="trace-stage observation"><span className="trace-index">01</span><div><span className="trace-label">LIVE OBSERVATION</span><b>{sensor?.vibration === null || sensor?.vibration === undefined ? 'Vibration channel unavailable' : `${sensor.vibration.toFixed(2)} ${sensor.unit} vibration`}</b><p>{sensor ? `${sensor.temperature.toFixed(1)} °C · ${sensor.humidity === null ? 'humidity unavailable' : `${sensor.humidity.toFixed(1)}% humidity`}` : 'Waiting for the newest reading.'}</p></div></li>
      <li className="trace-stage detected"><span className="trace-index">02</span><div><span className="trace-label">CONDITION DETECTED</span><b>{incident.detectors.length ? incident.detectors.map(display).join(' + ') : 'Condition under evaluation'}</b><p>{incident.decision ? `${display(incident.decision)} from live detector evidence and runtime policy.` : 'Policy decision is still being calculated.'}</p></div></li>
      <li className="trace-stage retrieval"><span className="trace-index">03</span><div><span className="trace-label">KNOWLEDGE MATCH</span><b>{precedent ? `${precedent.incident_id} · ${display(assessment?.likely_fault ?? precedent.fault_family)}` : 'No verified scenario match yet'}</b><p>{precedent ? precedent.summary : 'The agent will not name a fault without verified scenario evidence.'}</p><small>{precedent ? (precedent.source_kind === 'water_treatment_simulation' ? 'Curated water-treatment scenario' : display(precedent.source_kind)) : 'Retrieval remains evidence-gated'}</small></div></li>
      <li className="trace-stage assessment" aria-live="polite"><span className="trace-index">04</span><div><span className="trace-label">WARDEN ASSESSMENT</span><b>{assessment?.title ?? 'Evidence assessment in progress'}</b><p>{assessment?.explanation ?? 'Waiting for enough detector and scenario evidence to make a safe statement.'}</p><small>{modelLabel}</small></div></li>
      <li className="trace-stage recovery" aria-live="polite"><span className="trace-index">05</span><div><span className="trace-label">RECOVERY WATCH</span><b>{incident.agent_active ? display(incident.recovery_state ?? 'monitoring live telemetry') : 'Waiting for new telemetry'}</b><p>{recoveryMessage(incident)}</p></div></li>
    </ol>
    {incident.review ? <section className="trace-review"><span>OPERATOR DIAGNOSIS SAVED</span><b>{display(incident.review.outcome)}</b><p>{incident.review.notes}</p><small>{incident.review.knowledge_enriched ? 'Saved to local knowledge for future retrieval.' : 'Saved as an incident record.'}</small></section> : <section className="trace-handoff"><div><span>OPERATOR HANDOFF</span><b>Record the inspection finding</b><p>Confirmed repairs become labeled local knowledge for a future similar incident.</p></div><button className="agent-primary" type="button" onClick={() => setOpen((value) => !value)}>{open ? 'Close diagnosis workspace' : 'Record inspection finding'}<em>→</em></button></section>}
    {open && !incident.review ? <DiagnosisForm incident={incident} onReview={onReview} /> : null}
  </aside>
}
