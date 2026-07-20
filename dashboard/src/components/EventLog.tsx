import type { StreamEvent } from '../types/dashboard'

export function EventLog({ events }: { events: StreamEvent[] }) {
  return <section className="event-log"><div className="event-heading"><div><p className="eyebrow">STREAM ACTIVITY</p><h2>Recent events</h2></div><button className="text-button">View all activity →</button></div><div className="events-table"><div className="table-labels"><span>TIME</span><span>SOURCE</span><span>EVENT</span><span>DETAIL</span><span>STATUS</span></div>{events.map((event) => <div className="event-row" key={`${event.time}-${event.sensor}`}><time>{event.time}</time><span><b>{event.sensor}</b></span><span><b>{event.type}</b></span><span>{event.detail}</span><span className={`event-severity ${event.severity.toLowerCase()}`}>{event.severity}</span></div>)}</div></section>
}
