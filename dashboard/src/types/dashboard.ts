export type SensorState = 'normal' | 'watch' | 'critical' | 'offline'

export type Sensor = {
  device_id: string
  equipment: string
  area: string
  state: SensorState
  vibration: number | null
  temperature: number
  humidity: number
  fault_type: string
  fault_active: boolean
  duplicate: boolean
  lastSeen: string
  trend: number[]
}

export type StreamEvent = {
  time: string
  sensor: string
  type: string
  detail: string
  severity: 'Critical' | 'Watch' | 'Info'
}
