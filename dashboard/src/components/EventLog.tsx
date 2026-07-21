import type { Activity } from '../types/dashboard'

function eventDetail(activity: Activity) {
  const data = activity.data
  const source = String(data.device_id ?? data.incident_id ?? 'system')
  const detail = String(data.description ?? data.decision ?? data.status ?? data.category ?? 'Runtime state updated')
  const severity = String(data.severity ?? data.state ?? 'info').toLowerCase()
  const label = severity === 'high' || severity === 'critical' || severity === 'escalated' ? 'Critical' : severity === 'medium' || severity === 'recommended' ? 'Watch' : 'Info'
  return { source, detail, label }
}

export function EventLog({ events }: { events: Activity[] }) {
  return <section className="event-log"><div className="event-heading"><div><p className="eyebrow">RUNTIME ACTIVITY</p><h2>Recent events</h2></div><span className="retention-note">IN MEMORY · {events.length} EVENTS</span></div><div className="events-table"><div className="table-labels"><span>TIME</span><span>SOURCE</span><span>EVENT</span><span>DETAIL</span><span>STATUS</span></div>{events.length === 0 ? <div className="empty-row">No detector or incident activity yet.</div> : events.map((event, index) => { const item = eventDetail(event); return <div className="event-row" key={`${event.recorded_at}-${event.event}-${index}`}><time>{new Date(event.recorded_at * 1000).toLocaleTimeString()}</time><span><b>{item.source}</b></span><span><b>{event.event}</b></span><span>{item.detail}</span><span className={`event-severity ${item.label.toLowerCase()}`}>{item.label}</span></div> })}</div></section>
}
