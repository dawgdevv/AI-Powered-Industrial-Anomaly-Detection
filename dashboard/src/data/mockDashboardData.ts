import type { Sensor, StreamEvent } from '../types/dashboard'

// Replace these arrays with data returned by the streaming API.
// Sensor fields mirror the Python SensorReading schema.
export const sensors: Sensor[] = [
  { device_id: 'sensor-1', equipment: 'Pump P-04', area: 'Line 2 · Cooling', state: 'critical', vibration: 2.84, temperature: 68.2, humidity: 48.1, fault_type: 'anomaly', fault_active: true, duplicate: false, lastSeen: 'now', trend: [0.21, 0.24, 0.2, 0.28, 0.25, 0.31, 0.27, 0.34, 0.42, 0.58, 0.86, 1.38, 1.91, 2.44, 2.84] },
  { device_id: 'sensor-2', equipment: 'Mixer M-12', area: 'Line 2 · Blending', state: 'watch', vibration: 0.78, temperature: 54.7, humidity: 42.8, fault_type: 'drift', fault_active: true, duplicate: false, lastSeen: '4 sec ago', trend: [0.29, 0.3, 0.31, 0.33, 0.34, 0.36, 0.39, 0.42, 0.46, 0.5, 0.55, 0.61, 0.65, 0.72, 0.78] },
  { device_id: 'sensor-3', equipment: 'Fan F-07', area: 'Line 1 · Ventilation', state: 'offline', vibration: null, temperature: 31.6, humidity: 51.4, fault_type: 'MCAR', fault_active: true, duplicate: false, lastSeen: '1 min ago', trend: [0.19, 0.2, 0.23, 0.21, 0.22, 0.19, 0.21, 0.2, 0.18, 0.2, 0.19, 0.2, 0.18, 0.19, 0.18] },
  { device_id: 'sensor-4', equipment: 'Conveyor C-03', area: 'Line 1 · Packing', state: 'normal', vibration: 0.31, temperature: 39.3, humidity: 44.6, fault_type: 'duplicate_data', fault_active: false, duplicate: true, lastSeen: 'now', trend: [0.24, 0.27, 0.25, 0.29, 0.26, 0.28, 0.31, 0.29, 0.3, 0.27, 0.31, 0.3, 0.29, 0.32, 0.31] },
]

export const events: StreamEvent[] = [
  { time: '02:14:08', sensor: 'sensor-1', type: 'Vibration spike', detail: '2.84 mm/s · exceeds normal operating band', severity: 'Critical' },
  { time: '02:13:47', sensor: 'sensor-2', type: 'Gradual drift', detail: 'Upward shift sustained over 40 readings', severity: 'Watch' },
  { time: '02:13:12', sensor: 'sensor-3', type: 'Missing telemetry', detail: 'No reading received for 62 seconds', severity: 'Watch' },
  { time: '02:11:31', sensor: 'sensor-4', type: 'Duplicate reading', detail: 'Publisher retry detected; no equipment fault inferred', severity: 'Info' },
]
