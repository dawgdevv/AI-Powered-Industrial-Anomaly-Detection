import { useState } from 'react'
import type { Incident } from '../types/dashboard'

type Props = {
  incident?: Incident
  onAcknowledge: (id: string) => Promise<void>
  onResolve: (id: string) => Promise<void>
}

const decisionLabels = {
  RECOMMEND: 'Maintenance recommended',
  ESCALATE: 'Human review required',
  MONITOR: 'Continue monitoring',
  DATA_QUALITY_ALERT: 'Inspect data path',
}

export function IncidentAssessment({ incident, onAcknowledge, onResolve }: Props) {
  const [pending, setPending] = useState<'acknowledge' | 'resolve' | null>(null)

  if (!incident) {
    return <aside className="assessment-panel empty-assessment">
      <div className="panel-title"><div><p className="eyebrow">INCIDENT ASSESSMENT</p><h2>No active incident</h2></div><span className="agent-badge">Policy controlled</span></div>
      <p>Detector evidence and confidence decisions will appear here when the selected sensor crosses an anomaly rule.</p>
    </aside>
  }

  const act = async (action: 'acknowledge' | 'resolve') => {
    setPending(action)
    try {
      await (action === 'acknowledge' ? onAcknowledge(incident.incident_id) : onResolve(incident.incident_id))
    } finally {
      setPending(null)
    }
  }
  const confidence = Math.round(incident.confidence * 100)
  const decision = incident.decision ? decisionLabels[incident.decision] : 'Awaiting evidence'

  return <aside className="assessment-panel">
    <div className="panel-title"><div><p className="eyebrow">INCIDENT ASSESSMENT</p><h2>{incident.incident_id}</h2></div><span className={`incident-state ${incident.state.toLowerCase()}`}>{incident.state}</span></div>
    <div className="assessment-body">
      <div className="confidence"><div className="confidence-ring" style={{ '--confidence': `${confidence * 3.6}deg` } as React.CSSProperties}><strong>{confidence}</strong><span>%</span></div><div><span>POLICY CONFIDENCE</span><strong>{decision}</strong><p>{incident.affected_reading_count} affected readings</p></div></div>
      <div className="diagnosis"><span>CATEGORY</span><h3>{incident.category.replaceAll('_', ' ')}</h3><p>Evidence from {incident.detectors.length ? incident.detectors.join(', ') : 'no active detectors'}.</p></div>
      <div className="evidence-list"><span>REASON CODES</span>{incident.reason_codes.map((reason) => <code key={reason}>{reason}</code>)}</div>
      <div className="incident-facts"><span>Peak <b>{incident.peak_observed_value?.toFixed(3) ?? '—'}</b></span><span>Severity <b>{incident.peak_severity}</b></span></div>
      <button className={`review-button ${incident.acknowledged ? 'requested' : ''}`} disabled={incident.acknowledged || pending !== null} onClick={() => act('acknowledge')}>{incident.acknowledged ? '✓ Acknowledged' : pending === 'acknowledge' ? 'Acknowledging…' : 'Acknowledge incident'}</button>
      <button className="dismiss-button" disabled={incident.state === 'RESOLVED' || pending !== null} onClick={() => act('resolve')}>{incident.state === 'RESOLVED' ? 'Resolved' : pending === 'resolve' ? 'Resolving…' : 'Resolve incident'}</button>
    </div>
  </aside>
}
