import { useEffect, useState } from 'react'
import type { PolicyConfig } from '../types/dashboard'

type Props = { policy: PolicyConfig; onApply: (policy: PolicyConfig) => Promise<void> }

const fields: Array<{ key: keyof PolicyConfig; label: string; step: string }> = [
  { key: 'spike_weight', label: 'Spike weight', step: '0.05' },
  { key: 'drift_weight', label: 'Drift weight', step: '0.05' },
  { key: 'monitor_threshold', label: 'Monitor threshold', step: '0.05' },
  { key: 'recommend_threshold', label: 'Recommend threshold', step: '0.05' },
  { key: 'persistence_step', label: 'Persistence step', step: '0.01' },
  { key: 'max_persistence_bonus', label: 'Max persistence bonus', step: '0.05' },
  { key: 'data_quality_min_readings', label: 'Data-quality minimum', step: '1' },
]

export function PolicyControls({ policy, onApply }: Props) {
  const [draft, setDraft] = useState(policy)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  useEffect(() => setDraft(policy), [policy])

  const apply = async () => {
    setSaving(true)
    setError(null)
    try { await onApply(draft) } catch (cause) { setError(cause instanceof Error ? cause.message : 'Policy update failed') } finally { setSaving(false) }
  }

  return <section className="policy-panel"><div className="policy-heading"><div><p className="eyebrow">RUNTIME POLICY</p><h2>Detector agreement</h2></div><span>Resets when API restarts</span></div><div className="policy-fields">{fields.map((field) => <label key={field.key}><span>{field.label}</span><input type="number" min="0" max={field.key.includes('threshold') ? '1' : undefined} step={field.step} value={draft[field.key]} onChange={(event) => setDraft((current) => ({ ...current, [field.key]: field.key === 'data_quality_min_readings' ? Number.parseInt(event.target.value || '0', 10) : Number.parseFloat(event.target.value || '0') }))} /></label>)}</div>{error ? <p className="policy-error">{error}</p> : null}<div className="policy-actions"><button className="dismiss-button" onClick={() => setDraft(policy)} disabled={saving}>Reset changes</button><button className="review-button" onClick={apply} disabled={saving}>{saving ? 'Applying…' : 'Apply policy'}</button></div></section>
}
