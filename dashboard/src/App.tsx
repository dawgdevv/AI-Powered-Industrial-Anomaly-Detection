import { useMemo, useState } from 'react'
import { EventLog } from './components/EventLog'
import { FleetPanel } from './components/FleetPanel'
import { IncidentAssessment } from './components/IncidentAssessment'
import { PolicyControls } from './components/PolicyControls'
import { SensorDetail } from './components/SensorDetail'
import { useLiveDashboard } from './hooks/useLiveDashboard'
import type { SensorState } from './types/dashboard'
import './App.css'

const streamLabels = {
  connecting: 'Connecting to stream',
  connected: 'Stream connected',
  reconnecting: 'Stream reconnecting',
  unavailable: 'API unavailable',
}

function App() {
  const live = useLiveDashboard()
  const [selectedId, setSelectedId] = useState('sensor-1')
  const [filter, setFilter] = useState<'all' | SensorState>('all')
  const [view, setView] = useState<'operations' | 'activity'>('operations')
  const [policyOpen, setPolicyOpen] = useState(false)
  const selected = live.sensors.find((sensor) => sensor.device_id === selectedId) ?? live.sensors[0]
  const visibleSensors = useMemo(() => live.sensors.filter((sensor) => filter === 'all' || sensor.state === filter), [filter, live.sensors])
  const counts = useMemo(() => live.sensors.reduce<Record<SensorState, number>>((result, sensor) => { result[sensor.state] += 1; return result }, { normal: 0, watch: 0, critical: 0, offline: 0 }), [live.sensors])
  const selectedIncident = useMemo(() => {
    if (!selected) return undefined
    return live.incidents.find((incident) => incident.device_id === selected.device_id && incident.state !== 'RESOLVED')
      ?? live.incidents.find((incident) => incident.device_id === selected.device_id)
  }, [live.incidents, selected])
  const now = new Date()

  return <main className="plant-dashboard">
    <header className="topbar"><div className="brand"><span className="brand-mark">A</span>ANOMALY <b>CONTROL</b></div><nav className="top-nav" aria-label="Dashboard views"><button className={view === 'operations' ? 'active' : ''} onClick={() => setView('operations')}>Operations</button><button className={view === 'activity' ? 'active' : ''} onClick={() => setView('activity')}>Activity <b>{live.activity.length}</b></button></nav><div className="plant-name"><span className={`plant-dot ${live.streamStatus}`} /> Westfield Water Treatment Plant</div><div className="header-fleet" aria-label="Fleet condition filters"><button className={filter === 'critical' ? 'active critical' : 'critical'} onClick={() => setFilter(filter === 'critical' ? 'all' : 'critical')}><b>{counts.critical}</b> alarm</button><button className={filter === 'watch' ? 'active watch' : 'watch'} onClick={() => setFilter(filter === 'watch' ? 'all' : 'watch')}><b>{counts.watch}</b> watch</button><button className={filter === 'normal' ? 'active normal' : 'normal'} onClick={() => setFilter(filter === 'normal' ? 'all' : 'normal')}><b>{counts.normal}</b> normal</button></div><div className="top-actions"><time className="header-time" dateTime={now.toISOString()}>{now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</time><span className={`stream-status ${live.streamStatus}`}><i />{streamLabels[live.streamStatus]}</span><button className="policy-trigger" onClick={() => setPolicyOpen(true)} aria-haspopup="dialog" aria-expanded={policyOpen}>Runtime policy</button><button className="avatar" aria-label="Operator profile">NR</button></div></header>
    {live.streamError ? <div className="connection-banner"><b>{streamLabels[live.streamStatus]}.</b> {live.streamError}</div> : null}
    {view === 'operations' ? <><section className="page-heading operations-heading"><div><p className="eyebrow">OPERATIONS / SENSOR FLEET</p><h1>Equipment condition</h1><p>{live.loading ? 'Loading live telemetry.' : `${live.sensors.length} of ${live.fleetSize} assets reporting · live detector evidence and policy decisions.`}</p></div></section><section className="workspace"><FleetPanel sensors={visibleSensors} selectedId={selected?.device_id ?? ''} onSelect={setSelectedId} onShowAll={() => setFilter('all')} /><SensorDetail sensor={selected} incident={selectedIncident} /><IncidentAssessment incident={selectedIncident} onAcknowledge={live.acknowledge} onResolve={live.resolve} onReview={live.review} /></section></> : <section className="activity-page"><div className="page-heading"><div><p className="eyebrow">OPERATIONS / ACTIVITY LOG</p><h1>Runtime activity</h1><p>One chronological record of stream health, detector evidence, incidents, and operator actions.</p></div><div className="shift">LIVE EVENTS<strong>{live.activity.length}</strong><span>Newest first · retained in memory</span></div></div><EventLog events={live.activity} fullPage /></section>}
    {policyOpen ? <div className="policy-overlay" onMouseDown={() => setPolicyOpen(false)}><aside className="policy-drawer" role="dialog" aria-modal="true" aria-label="Runtime policy" onMouseDown={(event) => event.stopPropagation()}><div className="drawer-heading"><div><p className="eyebrow">RUNTIME CONTROLS</p><h2>Decision policy</h2></div><button onClick={() => setPolicyOpen(false)} aria-label="Close runtime policy">×</button></div><p className="drawer-note">Changes apply to the live runtime and are saved in SQLite for the next restart.</p><PolicyControls policy={live.policy} onApply={live.updatePolicy} /></aside></div> : null}
  </main>
}

export default App
