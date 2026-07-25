"""Privacy-safe OpenTelemetry traces, metrics, and incident lifecycle logs."""

from __future__ import annotations

from contextlib import contextmanager
import logging
import os
from time import perf_counter
from typing import Iterator

from opentelemetry import metrics, trace

_configured = False
_instruments: "TelemetryInstruments | None" = None
_providers: list[object] = []
_event_logger = logging.getLogger("iot_stream.events")


class TelemetryInstruments:
    """Low-cardinality operational measurements; never put raw readings here."""

    def __init__(self) -> None:
        meter = metrics.get_meter("iot_stream")
        self.readings = meter.create_counter("iot.readings", unit="1", description="Validated telemetry readings processed")
        self.anomalies = meter.create_counter("iot.anomalies", unit="1", description="Detector events by detector and severity")
        self.policy_decisions = meter.create_counter("policy.decisions", unit="1", description="Runtime safety-policy decisions by decision and incident category")
        self.retrievals = meter.create_counter("knowledge.retrievals", unit="1", description="Knowledge retrieval attempts by outcome")
        self.assessments = meter.create_counter("agent.assessments", unit="1", description="Agent assessments by provenance and outcome")
        self.auto_resolutions = meter.create_counter("agent.auto_resolutions", unit="1", description="Incidents automatically resolved after healthy telemetry")
        self.processing_duration = meter.create_histogram("iot.processing.duration", unit="s", description="End-to-end processing time for one reading")
        self.assessment_duration = meter.create_histogram("agent.assessment.duration", unit="s", description="Time spent generating an agent assessment")
        self.incident_duration = meter.create_histogram("incident.duration", unit="s", description="Open-to-auto-resolved incident duration")


def configure_telemetry() -> None:
    """Export OTLP telemetry when an endpoint is deliberately configured."""
    global _configured, _instruments
    if _configured:
        return
    _configured = True
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        return
    try:
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as error:
        raise RuntimeError("OTLP telemetry is configured but its SDK/exporter is missing; run uv sync") from error

    resource = Resource.create({
        "service.name": os.getenv("OTEL_SERVICE_NAME", "iot-anomaly-control"),
        "service.version": os.getenv("OTEL_SERVICE_VERSION", "0.1.0"),
        "service.namespace": os.getenv("OTEL_SERVICE_NAMESPACE", "water-treatment"),
        "deployment.environment.name": os.getenv("OTEL_DEPLOYMENT_ENVIRONMENT", "development"),
    })
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(tracer_provider)

    interval_ms = int(os.getenv("OTEL_METRIC_EXPORT_INTERVAL", "5000"))
    metric_provider = MeterProvider(
        resource=resource,
        metric_readers=[PeriodicExportingMetricReader(OTLPMetricExporter(), export_interval_millis=interval_ms)],
    )
    metrics.set_meter_provider(metric_provider)
    _instruments = TelemetryInstruments()

    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
    handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
    _event_logger.setLevel(logging.INFO)
    _event_logger.addHandler(handler)
    _event_logger.propagate = False
    _providers.extend((tracer_provider, metric_provider, logger_provider))


def shutdown_telemetry() -> None:
    """Flush pending OTLP batches before the FastAPI process exits."""
    for provider in reversed(_providers):
        shutdown = getattr(provider, "shutdown", None)
        if callable(shutdown):
            shutdown()


def health_status() -> dict[str, str]:
    """Return configuration state without attempting a blocking collector probe."""
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if endpoint and _instruments is not None:
        return {"state": "active", "detail": "OTLP traces, metrics, and logs are exporting"}
    if endpoint:
        return {"state": "degraded", "detail": "OTLP endpoint is configured but telemetry has not initialized"}
    return {"state": "standby", "detail": "Set OTEL_EXPORTER_OTLP_ENDPOINT to export to SigNoz"}


def current_trace_id() -> str | None:
    """Return the active W3C trace ID only when an SDK span is recording."""
    context = trace.get_current_span().get_span_context()
    return f"{context.trace_id:032x}" if context.is_valid else None


def _metrics() -> TelemetryInstruments | None:
    return _instruments


def event(name: str, **attributes: str | int | float | bool) -> None:
    """Emit one correlated business event without raw telemetry or repair notes."""
    if _configured and _instruments is not None:
        _event_logger.info(name, extra=attributes)


def record_reading(*, equipment_type: str, sensor_type: str) -> None:
    if instruments := _metrics():
        instruments.readings.add(1, {"equipment.type": equipment_type, "sensor.type": sensor_type})


def record_anomaly(*, detector: str, severity: str, category: str) -> None:
    if instruments := _metrics():
        instruments.anomalies.add(1, {"detector.name": detector, "anomaly.severity": severity, "incident.category": category})


def record_policy_decision(*, decision: str, incident_category: str) -> None:
    if instruments := _metrics():
        instruments.policy_decisions.add(1, {
            "policy.decision": decision,
            "incident.category": incident_category,
        })


def record_retrieval(*, equipment_type: str, matched: bool) -> None:
    if instruments := _metrics():
        instruments.retrievals.add(1, {"equipment.type": equipment_type, "knowledge.outcome": "matched" if matched else "no_match"})


def record_assessment(
    *, attempted_mode: str, final_mode: str, fallback: bool,
    abstained: bool, duration_seconds: float,
) -> None:
    if instruments := _metrics():
        attributes = {
            # agent.mode remains for existing dashboards; use attempted_mode to
            # distinguish a fast local result from a slow failed model attempt.
            "agent.mode": final_mode,
            "agent.attempted_mode": attempted_mode,
            "agent.final_mode": final_mode,
            "agent.fallback": fallback,
            "agent.outcome": "abstained" if abstained else "assessment_created",
        }
        instruments.assessments.add(1, attributes)
        instruments.assessment_duration.record(
            duration_seconds,
            {"agent.attempted_mode": attempted_mode, "agent.final_mode": final_mode},
        )


def record_auto_resolution(*, incident_category: str, duration_seconds: float) -> None:
    if instruments := _metrics():
        attributes = {"incident.category": incident_category}
        instruments.auto_resolutions.add(1, attributes)
        instruments.incident_duration.record(duration_seconds, attributes)


def record_processing_duration(*, equipment_type: str, duration_seconds: float) -> None:
    if instruments := _metrics():
        instruments.processing_duration.record(duration_seconds, {"equipment.type": equipment_type})


@contextmanager
def span(name: str, **attributes: str | int | float | bool) -> Iterator[trace.Span]:
    with trace.get_tracer("iot_stream").start_as_current_span(name) as active_span:
        for key, value in attributes.items():
            active_span.set_attribute(key, value)
        yield active_span


def elapsed_seconds(started_at: float) -> float:
    """Keep monotonic timing details out of pipeline modules."""
    return perf_counter() - started_at
