import { useEffect, useMemo, useState } from 'react'
import { EventLog } from './components/EventLog'
import { FleetPanel } from './components/FleetPanel'
import { IncidentAssessment } from './components/IncidentAssessment'
import { PolicyControls } from './components/PolicyControls'
import { SensorDetail } from './components/SensorDetail'
import { ServiceStatusPanel } from './components/ServiceStatusPanel'
import { useLiveDashboard } from './hooks/useLiveDashboard'
import type { SensorState } from './types/dashboard'
import './App.css'

const streamLabels = {
  connecting: 'Connecting to stream',
  connected: 'Live stream connected',
  reconnecting: 'Reconnecting to stream',
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
  const selectedIncident = useMemo(() => selected ? live.incidents.find((incident) => incident.device_id === selected.device_id && incident.state !== 'RESOLVED') : undefined, [live.incidents, selected])
  const latestResolved = useMemo(() => selected ? live.incidents.find((incident) => incident.device_id === selected.device_id && incident.state === 'RESOLVED') : undefined, [live.incidents, selected])
  const activeEquipmentIncident = useMemo(() => live.incidents.find((incident) => incident.category === 'EQUIPMENT_CONDITION' && incident.state !== 'RESOLVED'), [live.incidents])
  useEffect(() => {
    if (!activeEquipmentIncident || selectedIncident) return
    setSelectedId(activeEquipmentIncident.device_id)
  }, [activeEquipmentIncident, selectedIncident])
  const activeIncidents = live.incidents.filter((incident) => incident.state !== 'RESOLVED').length
  const now = new Date()

  return <main className="plant-dashboard command-center">
    <header className="topbar command-topbar">
      <div className="brand"><span className="brand-mark">A</span>ANOMALY <b>CONTROL</b></div>
      <nav className="top-nav" aria-label="Dashboard views"><button className={view === 'operations' ? 'active' : ''} onClick={() => setView('operations')}>Command center</button><button className={view === 'activity' ? 'active' : ''} onClick={() => setView('activity')}>Activity <b>{live.activity.length}</b></button></nav>
      <div className="plant-name"><span className={`plant-dot ${live.streamStatus}`} />Westfield Water Treatment Plant</div>
      <div className="top-actions"><time className="header-time" dateTime={now.toISOString()}>{now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</time><span className={`stream-status ${live.streamStatus}`}><i />{streamLabels[live.streamStatus]}</span><button className="policy-trigger" onClick={() => setPolicyOpen(true)} aria-haspopup="dialog" aria-expanded={policyOpen}>Runtime policy</button><button className="avatar" aria-label="Operator profile">NR</button></div>
    </header>
    {live.streamError ? <div className="connection-banner"><b>{streamLabels[live.streamStatus]}.</b> {live.streamError}</div> : null}
    {view === 'operations' ? <>
      <section className="command-heading">
        <div><p className="eyebrow">WESTFIELD / OPERATIONS COMMAND</p><h1>Plant condition, explained.</h1><p>{live.loading ? 'Loading live telemetry.' : `${live.sensors.length} of ${live.fleetSize} assets reporting · detector evidence, knowledge retrieval, and recovery are visible in one place.`}</p></div>
        <div className="command-counts" aria-label="Fleet condition filters"><button className={filter === 'critical' ? 'active critical' : 'critical'} onClick={() => setFilter(filter === 'critical' ? 'all' : 'critical')}><b>{counts.critical}</b><span>alarm</span></button><button className={filter === 'watch' ? 'active watch' : 'watch'} onClick={() => setFilter(filter === 'watch' ? 'all' : 'watch')}><b>{counts.watch}</b><span>watch</span></button><button className={filter === 'normal' ? 'active normal' : 'normal'} onClick={() => setFilter(filter === 'normal' ? 'all' : 'normal')}><b>{counts.normal}</b><span>normal</span></button><div><b>{activeIncidents}</b><span>active workflows</span></div></div>
      </section>
      <ServiceStatusPanel services={live.services} />
      <section className="command-workspace">
        <FleetPanel sensors={visibleSensors} selectedId={selected?.device_id ?? ''} onSelect={setSelectedId} onShowAll={() => setFilter('all')} />
        <div className="command-evidence"><SensorDetail sensor={selected} incident={selectedIncident} /><EventLog events={live.activity} limit={7} /></div>
        <IncidentAssessment incident={selectedIncident} resolvedIncident={latestResolved} sensor={selected} onReview={live.review} />
      </section>
    </> : <section className="activity-page"><div className="page-heading"><div><p className="eyebrow">OPERATIONS / ACTIVITY LOG</p><h1>Runtime activity</h1><p>One chronological record of stream health, detector evidence, incidents, and operator actions.</p></div><div className="shift">LIVE EVENTS<strong>{live.activity.length}</strong><span>Newest first · retained in memory</span></div></div><EventLog events={live.activity} fullPage /></section>}
    {policyOpen ? <div className="policy-overlay" onMouseDown={() => setPolicyOpen(false)}><aside className="policy-drawer" role="dialog" aria-modal="true" aria-label="Runtime policy" onMouseDown={(event) => event.stopPropagation()}><div className="drawer-heading"><div><p className="eyebrow">RUNTIME CONTROLS</p><h2>Decision policy</h2></div><button onClick={() => setPolicyOpen(false)} aria-label="Close runtime policy">×</button></div><p className="drawer-note">Changes apply to the live runtime and are saved in SQLite for the next restart.</p><PolicyControls policy={live.policy} onApply={live.updatePolicy} /></aside></div> : null}
  </main>
}

export default App
