import type { Sensor, SensorState } from '../types/dashboard'

const labels: Record<SensorState, string> = { normal: 'Normal', watch: 'Watch', critical: 'Critical', offline: 'No signal' }

function TrendChart({ trend, state }: Pick<Sensor, 'trend' | 'state'>) {
  const max = Math.max(...trend, 3)
  const points = trend.map((value, index) => `${(index / (trend.length - 1)) * 100},${92 - (value / max) * 76}`).join(' ')
  return <svg viewBox="0 0 100 100" className={`trend-chart ${state}`} preserveAspectRatio="none" aria-label="Vibration trend"><line x1="0" x2="100" y1="48" y2="48" className="threshold" /><polyline points={points} className="trend-line" /></svg>
}

export function SensorDetail({ sensor }: { sensor: Sensor }) {
  return <section className="detail-panel"><div className="detail-heading"><div><p className="eyebrow">{sensor.device_id} / {sensor.area}</p><h2>{sensor.equipment}</h2></div><span className={`pill ${sensor.state}`}>{labels[sensor.state]}</span></div><div className="reading-grid"><div className="primary-reading"><span>VIBRATION</span><strong>{sensor.vibration === null ? '—' : sensor.vibration.toFixed(2)} <small>mm/s</small></strong><p>{sensor.vibration === null ? 'Last reading unavailable' : sensor.state === 'critical' ? 'Above intervention limit' : 'Current reading'}</p></div><div className="metric"><span>TEMPERATURE</span><strong>{sensor.temperature.toFixed(1)}<small>°C</small></strong><p>Expected range: 20–75°C</p></div><div className="metric"><span>HUMIDITY</span><strong>{sensor.humidity.toFixed(1)}<small>%</small></strong><p>Expected range: 35–65%</p></div></div><div className="chart-section"><div className="chart-meta"><div><span>VIBRATION · LAST 90 SECONDS</span><strong>{sensor.state === 'critical' ? 'Intervention limit: 1.20 mm/s' : 'Normal operating band'}</strong></div><span className="live-label"><i /> LIVE</span></div><TrendChart trend={sensor.trend} state={sensor.state} /><div className="chart-axis"><span>−90s</span><span>−60s</span><span>−30s</span><span>NOW</span></div></div><div className="data-note">Last stream message <b>{sensor.lastSeen}</b> · Fault mode: <b>{sensor.fault_type}</b></div></section>
}
