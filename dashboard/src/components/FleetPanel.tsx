import type { Sensor } from '../types/dashboard'

type Props = { sensors: Sensor[]; selectedId: string; onSelect: (id: string) => void; onShowAll: () => void }

export function FleetPanel({ sensors, selectedId, onSelect, onShowAll }: Props) {
  return <aside className="fleet-panel"><div className="panel-title"><div><p className="eyebrow">LIVE FLEET</p><h2>Sensors <span>{sensors.length}</span></h2></div><button className="text-button" onClick={onShowAll}>Show all</button></div><div className="sensor-list">{sensors.map((sensor) => <button key={sensor.device_id} className={`sensor-row ${selectedId === sensor.device_id ? 'selected' : ''}`} onClick={() => onSelect(sensor.device_id)}><span className={`sensor-state ${sensor.state}`} /><span className="sensor-copy"><strong>{sensor.equipment}</strong><small>{sensor.device_id} · {sensor.area}</small></span><span className="sensor-reading"><b>{sensor.vibration === null ? '—' : sensor.vibration.toFixed(2)}</b><small>{sensor.vibration === null ? 'NO SIGNAL' : 'mm/s'}</small></span></button>)}</div><div className="legend"><span><i className="normal" />Normal</span><span><i className="watch" />Watch</span><span><i className="critical" />Critical</span></div></aside>
}
