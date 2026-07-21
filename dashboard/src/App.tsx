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
    <header className="topbar"><div className="brand"><span className="brand-mark">A</span>ANOMALY <b>CONTROL</b></div><div className="plant-name"><span className={`plant-dot ${live.streamStatus}`} /> Westfield Plant <span>/ Live operations</span></div><div className="top-actions"><span className={`stream-status ${live.streamStatus}`}><i />{streamLabels[live.streamStatus]}</span><button className="avatar" aria-label="Operator profile">NR</button></div></header>
    {live.streamError ? <div className="connection-banner"><b>{streamLabels[live.streamStatus]}.</b> {live.streamError}</div> : null}
    <section className="page-heading"><div><p className="eyebrow">OPERATIONS / SENSOR FLEET</p><h1>Equipment condition</h1><p>Live detector evidence and runtime policy decisions.</p></div><div className="shift">LOCAL TIME<strong>{now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</strong><span>{now.toLocaleDateString([], { weekday: 'long', day: 'numeric', month: 'long' })}</span></div></section>
    <section className="overview"><StatusCount state="critical" label="Needs attention" value={counts.critical} active={filter === 'critical'} onClick={() => setFilter(filter === 'critical' ? 'all' : 'critical')} /><StatusCount state="watch" label="Watching closely" value={counts.watch} active={filter === 'watch'} onClick={() => setFilter(filter === 'watch' ? 'all' : 'watch')} /><StatusCount state="normal" label="Operating normally" value={counts.normal} active={filter === 'normal'} onClick={() => setFilter(filter === 'normal' ? 'all' : 'normal')} /><div className="fleet-coverage">FLEET COVERAGE<strong>{live.sensors.length} <small>/ 4</small></strong><span>{live.loading ? 'loading runtime state' : 'reporting devices'}</span></div></section>
    <section className="workspace"><FleetPanel sensors={visibleSensors} selectedId={selected?.device_id ?? ''} onSelect={setSelectedId} onShowAll={() => setFilter('all')} /><SensorDetail sensor={selected} /><IncidentAssessment incident={selectedIncident} onAcknowledge={live.acknowledge} onResolve={live.resolve} /></section>
    <PolicyControls policy={live.policy} onApply={live.updatePolicy} />
    <EventLog events={live.activity} />
  </main>
}

function StatusCount({ state, label, value, active, onClick }: { state: SensorState; label: string; value: number; active: boolean; onClick: () => void }) {
  return <button className={`overview-item ${active ? 'active' : ''}`} onClick={onClick}><i className={state} /><div><strong>{value}</strong><span>{label}</span></div></button>
}

export default App
