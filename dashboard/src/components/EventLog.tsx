import { useMemo, useState } from 'react'
import type { Activity } from '../types/dashboard'

function eventDetail(activity: Activity) {
  const data = activity.data
  const source = String(data.device_id ?? data.incident_id ?? 'system')
  const detail = String(data.description ?? data.decision ?? data.status ?? data.category ?? 'Runtime state updated')
  const severity = String(data.severity ?? data.state ?? 'info').toLowerCase()
  const label = severity === 'high' || severity === 'critical' || severity === 'escalated' ? 'Critical' : severity === 'medium' || severity === 'recommended' ? 'Watch' : 'Info'
  return { source, detail, label }
}

export function EventLog({ events, fullPage = false }: { events: Activity[]; fullPage?: boolean }) {
  const [filter, setFilter] = useState<'all' | 'alarm' | 'detector' | 'stream'>('all')
  const [search, setSearch] = useState('')
  const visibleEvents = useMemo(() => events.filter((event) => {
    const detail = eventDetail(event)
    const inGroup = filter === 'all' || (filter === 'alarm' && detail.label !== 'Info') || (filter === 'detector' && event.event === 'detector.triggered') || (filter === 'stream' && event.event === 'stream.status')
    return inGroup && `${event.event} ${detail.source} ${detail.detail}`.toLowerCase().includes(search.toLowerCase())
  }), [events, filter, search])
  return <section className={`event-log ${fullPage ? 'full-page' : ''}`}><div className="event-heading"><div><p className="eyebrow">RUNTIME ACTIVITY</p><h2>{fullPage ? 'Event history' : 'Recent events'}</h2></div><span className="retention-note">IN MEMORY · {events.length} EVENTS</span></div>{fullPage ? <div className="activity-toolbar"><div className="activity-filters">{(['all', 'alarm', 'detector', 'stream'] as const).map((option) => <button key={option} className={filter === option ? 'active' : ''} onClick={() => setFilter(option)}>{option === 'all' ? 'All events' : option}</button>)}</div><label><span className="eyebrow">SEARCH LOG</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Asset, event, or decision" /></label></div> : null}<div className="events-table"><div className="table-labels"><span>TIME</span><span>SOURCE</span><span>EVENT</span><span>DETAIL</span><span>STATUS</span></div>{visibleEvents.length === 0 ? <div className="empty-row">No matching runtime activity.</div> : visibleEvents.map((event, index) => { const item = eventDetail(event); return <div className="event-row" key={`${event.recorded_at}-${event.event}-${index}`}><time>{new Date(event.recorded_at * 1000).toLocaleTimeString()}</time><span><b>{item.source}</b></span><span><b>{event.event}</b></span><span>{item.detail}</span><span className={`event-severity ${item.label.toLowerCase()}`}>{item.label}</span></div> })}</div></section>
}
