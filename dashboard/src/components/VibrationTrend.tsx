import type { Incident, SensorState } from '../types/dashboard'

type Props = {
  trend: Array<number | null>
  state: SensorState
  unit: string
  incident?: Incident
}

type ConditionModel = {
  baseline: number
  spread: number
  minimum: number
  maximum: number
  warning: number
  alarm: number
}

function mean(values: number[]) {
  return values.reduce((total, value) => total + value, 0) / values.length
}

function modelTrend(trend: Array<number | null>): ConditionModel | null {
  const valid = trend.filter((value): value is number => value !== null)
  if (valid.length < 5) return null
  // Use the earlier samples as the display reference so the newest excursion is visible.
  const reference = valid.slice(0, Math.max(3, Math.floor(valid.length * 0.7)))
  const baseline = mean(reference)
  const spread = Math.max(Math.sqrt(mean(reference.map((value) => (value - baseline) ** 2))), baseline * 0.03, 0.01)
  const warning = baseline + spread * 2
  const alarm = baseline + spread * 3
  const values = [...valid, baseline - spread * 2, alarm]
  return { baseline, spread, warning, alarm, minimum: Math.min(...values), maximum: Math.max(...values) }
}

function toY(value: number, model: ConditionModel) {
  const range = Math.max(model.maximum - model.minimum, 0.01)
  return 54 - ((value - model.minimum) / range) * 46
}

function signalPath(trend: Array<number | null>, model: ConditionModel) {
  const denominator = Math.max(trend.length - 1, 1)
  let started = false
  return trend.map((value, index) => {
    if (value === null) { started = false; return '' }
    const command = started ? 'L' : 'M'
    started = true
    return `${command}${((index / denominator) * 100).toFixed(2)},${toY(value, model).toFixed(2)}`
  }).join(' ')
}

function readingLabel(value: number, unit: string) {
  return `${value.toFixed(2)} ${unit}`
}

export function VibrationTrend({ trend, state, unit, incident }: Props) {
  const model = modelTrend(trend)
  if (!model) {
    return <div className="baseline-learning" role="status"><strong>Baseline learning</strong><span>{trend.filter((value) => value !== null).length} of 5 valid readings received. Limits will appear once the operating pattern is established.</span></div>
  }

  const upperBand = toY(model.baseline + model.spread, model)
  const lowerBand = toY(model.baseline - model.spread, model)
  const baselineY = toY(model.baseline, model)
  const warningY = toY(model.warning, model)
  const alarmY = toY(model.alarm, model)
  const current = [...trend].reverse().find((value): value is number => value !== null)
  const deviation = current === undefined ? null : current - model.baseline

  return <>
    <div className="condition-summary">
      <span><b>{readingLabel(model.baseline, unit)}</b> learned baseline</span>
      <span><b>{deviation === null ? '—' : `${deviation >= 0 ? '+' : ''}${deviation.toFixed(2)} ${unit}`}</b> current deviation</span>
      <span><b>{readingLabel(model.warning, unit)}</b> guidance warning</span>
    </div>
    <svg viewBox="0 0 100 60" className={`condition-trend ${state}`} preserveAspectRatio="none" role="img" aria-label="Vibration condition trend with learned baseline and guidance limits">
      <rect x="0" y={upperBand} width="100" height={Math.max(lowerBand - upperBand, 0.4)} className="expected-band" />
      {[12, 28, 44].map((y) => <line key={y} x1="0" x2="100" y1={y} y2={y} className="trend-grid" />)}
      <line x1="0" x2="100" y1={baselineY} y2={baselineY} className="baseline-line" />
      <line x1="0" x2="100" y1={warningY} y2={warningY} className="warning-line" />
      <line x1="0" x2="100" y1={alarmY} y2={alarmY} className="alarm-line" />
      <path d={signalPath(trend, model)} className="signal-line" />
      {incident && incident.state !== 'RESOLVED' ? <g className="incident-marker"><line x1="98" x2="98" y1="5" y2="54" /><circle cx="98" cy={current === undefined ? 54 : toY(current, model)} r="1.8" /></g> : null}
      <text x="1" y={Math.max(5, warningY - 1)} className="trend-label">WATCH</text>
      <text x="1" y={Math.max(5, alarmY - 1)} className="trend-label alarm">ALARM</text>
    </svg>
    <div className="trend-key"><span><i className="signal-key" />Actual signal</span><span><i className="baseline-key" />Learned baseline</span><span><i className="band-key" />Expected band</span><span><i className="limit-key" />Guidance limits</span></div>
    <p className="trend-disclaimer">Display guidance only. Machine protection limits remain owned by plant controls.</p>
  </>
}
