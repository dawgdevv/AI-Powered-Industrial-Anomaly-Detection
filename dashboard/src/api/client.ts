import type { Activity, Health, Incident, PolicyConfig, Sensor } from '../types/dashboard'

const REQUEST_TIMEOUT_MS = 8_000

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
  let response: Response
  try {
    response = await fetch(path, { ...init, signal: controller.signal })
  } catch (cause) {
    if (controller.signal.aborted) throw new Error(`Request timed out for ${path}`)
    throw cause
  } finally {
    window.clearTimeout(timeout)
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const detail = body?.detail
    const message = Array.isArray(detail)
      ? detail.map((item: { msg?: string }) => item.msg).filter(Boolean).join(', ')
      : typeof detail === 'string' ? detail : `Request failed (${response.status})`
    throw new Error(message)
  }
  return response.json() as Promise<T>
}

export const api = {
  snapshots: () => Promise.all([
    request<Sensor[]>('/api/sensors'),
    request<Incident[]>('/api/incidents'),
    request<Activity[]>('/api/activity'),
    request<PolicyConfig>('/api/policy'),
    request<Health>('/api/health'),
  ]),
  updatePolicy: (policy: PolicyConfig) => request<PolicyConfig>('/api/policy', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(policy),
  }),
  review: (incidentId: string, outcome: 'confirmed_fault' | 'false_alarm' | 'different_cause', notes: string) => request<Incident>(`/api/incidents/${incidentId}/review`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ outcome, notes }) }),
}
