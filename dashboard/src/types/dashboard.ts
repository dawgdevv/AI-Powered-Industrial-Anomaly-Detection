export type SensorState = 'normal' | 'watch' | 'critical' | 'offline'
export type StreamStatus = 'connecting' | 'connected' | 'reconnecting' | 'unavailable'

export type Sensor = {
  event_id: string
  sequence_number: number
  device_id: string
  asset_id: string
  equipment_type: string
  equipment_name: string
  area: string
  sensor_type: string
  unit: string
  state: SensorState
  timestamp: number
  vibration: number | null
  temperature: number
  humidity: number | null
  trend: Array<number | null>
}

export type SensorUpdate = Omit<Sensor, 'trend'>

export type Incident = {
  incident_id: string
  device_id: string
  category: 'EQUIPMENT_CONDITION' | 'DATA_QUALITY'
  state: 'OPEN' | 'INVESTIGATING' | 'RECOMMENDED' | 'ESCALATED' | 'RESOLVED'
  first_seen: number
  last_seen: number
  affected_reading_count: number
  detectors: string[]
  peak_severity: string
  peak_observed_value: number | null
  confidence: number
  decision: 'RECOMMEND' | 'ESCALATE' | 'MONITOR' | 'DATA_QUALITY_ALERT' | null
  reason_codes: string[]
  acknowledged: boolean
  manually_resolved: boolean
  retrieved_incident_ids?: string[]
  retrieval_top_distance?: number | null
  retrieval_second_distance?: number | null
  retrieval_evidence?: Array<{ incident_id: string; distance: number | null; verified: boolean; source_url: string; summary: string }>
  review?: { outcome: 'confirmed_fault' | 'false_alarm' | 'different_cause'; notes: string; reviewed_at: number } | null
}

export type PolicyConfig = {
  spike_weight: number
  drift_weight: number
  monitor_threshold: number
  recommend_threshold: number
  persistence_step: number
  max_persistence_bonus: number
  data_quality_min_readings: number
}

export type Activity = {
  event: string
  recorded_at: number
  data: Record<string, unknown>
}

export type Health = {
  api: string
  stream_status: StreamStatus
  stream_error: string | null
  last_reading_at: number | null
  sensor_count: number
  configured_fleet_size: number
  incident_count: number
}
