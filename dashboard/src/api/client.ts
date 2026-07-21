import type { Activity, Health, Incident, PolicyConfig, Sensor } from '../types/dashboard'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
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
  acknowledge: (incidentId: string) => request<Incident>(`/api/incidents/${incidentId}/acknowledge`, { method: 'POST' }),
  resolve: (incidentId: string) => request<Incident>(`/api/incidents/${incidentId}/resolve`, { method: 'POST' }),
}
