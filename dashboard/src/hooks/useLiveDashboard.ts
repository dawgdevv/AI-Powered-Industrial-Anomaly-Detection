import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import type { Activity, Incident, PolicyConfig, Sensor, SensorUpdate, ServiceStatus, StreamStatus } from '../types/dashboard'

const EMPTY_POLICY: PolicyConfig = {
  spike_weight: 0.45,
  drift_weight: 0.55,
  monitor_threshold: 0.4,
  recommend_threshold: 0.75,
  persistence_step: 0.05,
  max_persistence_bonus: 0.15,
  data_quality_min_readings: 2,
}

function upsertById<T>(items: T[], next: T, key: keyof T): T[] {
  const index = items.findIndex((item) => item[key] === next[key])
  if (index === -1) return [next, ...items]
  const copy = items.slice()
  copy[index] = next
  return copy
}

export function useLiveDashboard() {
  const [sensors, setSensors] = useState<Sensor[]>([])
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [activity, setActivity] = useState<Activity[]>([])
  const [policy, setPolicy] = useState<PolicyConfig>(EMPTY_POLICY)
  const [streamStatus, setStreamStatus] = useState<StreamStatus>('connecting')
  const [streamError, setStreamError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [fleetSize, setFleetSize] = useState(6)
  const [services, setServices] = useState<ServiceStatus[]>([])
  const pendingSensors = useRef(new Map<string, SensorUpdate>())
  const flushTimer = useRef<number | null>(null)
  const latestSnapshot = useRef(0)
  const lastLiveEventAt = useRef(Date.now())

  const pushActivity = useCallback((event: string, data: Record<string, unknown>) => {
    setActivity((current) => [
      { event, recorded_at: Date.now() / 1000, data },
      ...current,
    ].slice(0, 50))
  }, [])

  const queueSensor = useCallback((sensor: SensorUpdate) => {
    pendingSensors.current.set(sensor.device_id, sensor)
    if (flushTimer.current !== null) return
    flushTimer.current = window.setTimeout(() => {
      const pending = [...pendingSensors.current.values()]
      pendingSensors.current.clear()
      flushTimer.current = null
      setSensors((current) => {
        let next = current
        for (const sensorUpdate of pending) {
          const existing = next.find((sensor) => sensor.device_id === sensorUpdate.device_id)
          const trend = [...(existing?.trend ?? []), sensorUpdate.vibration].slice(-90)
          next = upsertById(next, { ...existing, ...sensorUpdate, trend } as Sensor, 'device_id')
        }
        return next.toSorted((a, b) => a.device_id.localeCompare(b.device_id))
      })
    }, 100)
  }, [])

  useEffect(() => {
    let cancelled = false
    let source: EventSource | null = null
    let recoveryTimer: number | null = null

    const refreshSnapshots = async () => {
      const snapshotVersion = ++latestSnapshot.current
      try {
        const [sensorData, incidentData, activityData, policyData, health] = await api.snapshots()
        if (cancelled || snapshotVersion !== latestSnapshot.current) return
        setSensors(sensorData)
        setIncidents(incidentData)
        setActivity(activityData)
        setPolicy(policyData)
        setStreamStatus(health.stream_status)
        setStreamError(health.stream_error)
        setFleetSize(health.configured_fleet_size)
        setServices(health.services)
      } catch (cause) {
        const error = cause instanceof Error ? cause : new Error('API snapshot failed')
        if (!cancelled) {
          setStreamStatus('unavailable')
          setStreamError(error.message)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void refreshSnapshots()

    source = new EventSource('/api/stream')
    source.onopen = () => {
      lastLiveEventAt.current = Date.now()
      setStreamError(null)
      void refreshSnapshots()
    }
    source.onerror = () => {
      setStreamStatus('reconnecting')
      setStreamError('Live API connection interrupted')
    }
    source.addEventListener('sensor.updated', (event) => {
      lastLiveEventAt.current = Date.now()
      queueSensor(JSON.parse(event.data) as SensorUpdate)
    })
    for (const eventName of ['incident.updated', 'incident.resolved', 'incident.recovery_updated', 'incident.agent_resolved', 'incident.assessment_updated', 'incident.reviewed']) {
      source.addEventListener(eventName, (event) => {
        lastLiveEventAt.current = Date.now()
        const incident = JSON.parse(event.data) as Incident
        setIncidents((current) => upsertById(current, incident, 'incident_id'))
        pushActivity(eventName, incident as unknown as Record<string, unknown>)
      })
    }
    source.addEventListener('policy.updated', (event) => {
      lastLiveEventAt.current = Date.now()
      const updatedPolicy = JSON.parse(event.data) as PolicyConfig
      setPolicy(updatedPolicy)
      pushActivity('policy.updated', updatedPolicy as unknown as Record<string, unknown>)
    })
    source.addEventListener('stream.status', (event) => {
      lastLiveEventAt.current = Date.now()
      const status = JSON.parse(event.data) as { status: StreamStatus; error: string | null }
      setStreamStatus(status.status)
      setStreamError(status.error)
      pushActivity('stream.status', status as unknown as Record<string, unknown>)
    })
    source.addEventListener('detector.triggered', (event) => {
      lastLiveEventAt.current = Date.now()
      const data = JSON.parse(event.data) as Record<string, unknown>
      pushActivity('detector.triggered', data)
    })
    source.addEventListener('stream.connected', () => {
      lastLiveEventAt.current = Date.now()
    })

    // This is not polling: it only recovers a browser/proxy connection that
    // reports itself open but has stopped delivering the live stream.
    recoveryTimer = window.setInterval(() => {
      const streamIsStale = Date.now() - lastLiveEventAt.current > 8_000
      if (!streamIsStale || cancelled) return
      setStreamStatus('reconnecting')
      setStreamError('Live updates paused; refreshing the current system state')
      lastLiveEventAt.current = Date.now()
      void refreshSnapshots()
    }, 4_000)

    return () => {
      cancelled = true
      source?.close()
      if (flushTimer.current !== null) window.clearTimeout(flushTimer.current)
      if (recoveryTimer !== null) window.clearInterval(recoveryTimer)
    }
  }, [pushActivity, queueSensor])

  const updatePolicy = useCallback(async (next: PolicyConfig) => {
    const updated = await api.updatePolicy(next)
    setPolicy(updated)
  }, [])

  const review = useCallback(async (incidentId: string, outcome: 'confirmed_fault' | 'false_alarm' | 'different_cause', notes: string) => {
    const updated = await api.review(incidentId, outcome, notes)
    setIncidents((current) => upsertById(current, updated, 'incident_id'))
  }, [])

  return { sensors, incidents, activity, policy, streamStatus, streamError, loading, fleetSize, services, updatePolicy, review }
}
