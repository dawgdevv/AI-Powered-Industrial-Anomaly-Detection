import type { ServiceStatus } from '../types/dashboard'

export function ServiceStatusPanel({ services }: { services: ServiceStatus[] }) {
  return <section className="service-rack" aria-label="System service status">
    <div className="service-rack-heading"><div><p className="eyebrow">SYSTEM SERVICES</p><h2>Command readiness</h2></div><span>{services.filter((service) => service.state === 'active').length}/{services.length || 7} active</span></div>
    <div className="service-list">
      {services.map((service) => <article className={`service-item ${service.state}`} key={service.id} title={service.detail}>
        <i aria-hidden="true" /><div><b>{service.name}</b><small>{service.detail}</small></div><span>{service.state}</span>
      </article>)}
    </div>
  </section>
}
