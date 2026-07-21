import type { Sensor, SensorState } from '../types/dashboard'

const labels: Record<SensorState, string> = { normal: 'Normal', watch: 'Watch', critical: 'Critical', offline: 'No signal' }

function TrendChart({ trend, state }: Pick<Sensor, 'trend' | 'state'>) {
  const values = trend.map((value) => value ?? 0)
  const max = Math.max(...values, 1.2)
  const denominator = Math.max(values.length - 1, 1)
  const points = values.map((value, index) => `${(index / denominator) * 100},${92 - (value / max) * 76}`).join(' ')
  return <svg viewBox="0 0 100 100" className={`trend-chart ${state}`} preserveAspectRatio="none" aria-label="Vibration trend"><line x1="0" x2="100" y1="48" y2="48" className="threshold" /><polyline points={points} className="trend-line" /></svg>
}

export function SensorDetail({ sensor }: { sensor?: Sensor }) {
  if (!sensor) return <section className="detail-panel empty-detail"><p className="eyebrow">SENSOR DETAIL</p><h2>Waiting for stream</h2><p>Start the producer and API to populate live telemetry.</p></section>
  const lastSeenSeconds = Math.max(0, Date.now() / 1000 - sensor.timestamp)
  return <section className="detail-panel"><div className="detail-heading"><div><p className="eyebrow">{sensor.device_id} / {sensor.area}</p><h2>{sensor.equipment}</h2></div><span className={`pill ${sensor.state}`}>{labels[sensor.state]}</span></div><div className="reading-grid"><div className="primary-reading"><span>VIBRATION</span><strong>{sensor.vibration === null ? '—' : sensor.vibration.toFixed(2)} <small>{sensor.unit}</small></strong><p>{sensor.vibration === null ? 'Latest channel value is missing' : 'Current validated reading'}</p></div><div className="metric"><span>TEMPERATURE</span><strong>{sensor.temperature.toFixed(1)}<small>°C</small></strong><p>Live channel</p></div><div className="metric"><span>HUMIDITY</span><strong>{sensor.humidity === null ? '—' : sensor.humidity.toFixed(1)}<small>%</small></strong><p>Live channel</p></div></div><div className="chart-section"><div className="chart-meta"><div><span>VIBRATION · LAST {sensor.trend.length} READINGS</span><strong>Bounded runtime history</strong></div><span className="live-label"><i /> LIVE</span></div><TrendChart trend={sensor.trend} state={sensor.state} /><div className="chart-axis"><span>OLDER</span><span>NOW</span></div></div><div className="data-note">Sequence <b>{sensor.sequence_number}</b> · Last stream message <b>{lastSeenSeconds < 2 ? 'now' : `${Math.round(lastSeenSeconds)}s ago`}</b></div></section>
}
