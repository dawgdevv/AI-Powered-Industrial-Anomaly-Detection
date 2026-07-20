import { useMemo, useState } from 'react'
import { EventLog } from './components/EventLog'
import { FleetPanel } from './components/FleetPanel'
import { IncidentAssessment } from './components/IncidentAssessment'
import { SensorDetail } from './components/SensorDetail'
import { events, sensors } from './data/mockDashboardData'
import type { SensorState } from './types/dashboard'
import './App.css'

function App() {
  const [selectedId, setSelectedId] = useState('sensor-1')
  const [filter, setFilter] = useState<'all' | SensorState>('all')
  const [reviewRequested, setReviewRequested] = useState(false)
  const selected = sensors.find((sensor) => sensor.device_id === selectedId) ?? sensors[0]
  const visibleSensors = useMemo(() => sensors.filter((sensor) => filter === 'all' || sensor.state === filter), [filter])
  const count = (state: SensorState) => sensors.filter((sensor) => sensor.state === state).length

  return <main className="plant-dashboard"><header className="topbar"><div className="brand"><span className="brand-mark">A</span>ANOMALY <b>CONTROL</b></div><div className="plant-name"><span className="plant-dot" /> Westfield Plant <span>/ Live operations</span></div><div className="top-actions"><span className="stream-status"><i /> Stream connected</span><button className="avatar">NR</button></div></header><section className="page-heading"><div><p className="eyebrow">OPERATIONS / SENSOR FLEET</p><h1>Equipment condition</h1><p>Monitor live telemetry and act on evidence, not noise.</p></div><div className="shift">SHIFT A<strong>02:14 <small>LOCAL</small></strong><span>Tuesday, 18 June</span></div></section><section className="overview"><StatusCount state="critical" label="Needs attention" value={count('critical')} active={filter === 'critical'} onClick={() => setFilter(filter === 'critical' ? 'all' : 'critical')} /><StatusCount state="watch" label="Watching closely" value={count('watch')} active={filter === 'watch'} onClick={() => setFilter(filter === 'watch' ? 'all' : 'watch')} /><StatusCount state="normal" label="Operating normally" value={count('normal')} active={filter === 'normal'} onClick={() => setFilter(filter === 'normal' ? 'all' : 'normal')} /><div className="fleet-coverage">FLEET COVERAGE<strong>4 <small>/ 4</small></strong><span>reporting devices</span></div></section><section className="workspace"><FleetPanel sensors={visibleSensors} selectedId={selected.device_id} onSelect={setSelectedId} onShowAll={() => setFilter('all')} /><SensorDetail sensor={selected} /><IncidentAssessment requested={reviewRequested} onRequestReview={() => setReviewRequested(true)} /></section><EventLog events={events} /></main>
}

function StatusCount({ state, label, value, active, onClick }: { state: SensorState; label: string; value: number; active: boolean; onClick: () => void }) {
  return <button className={`overview-item ${active ? 'active' : ''}`} onClick={onClick}><i className={state} /><div><strong>{value}</strong><span>{label}</span></div></button>
}

export default App
