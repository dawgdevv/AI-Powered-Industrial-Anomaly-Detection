"""Small OpenTelemetry seam; exporter setup comes with the SigNoz slice."""

from contextlib import contextmanager
from typing import Iterator

from opentelemetry import trace

TRACER = trace.get_tracer("iot_stream")


@contextmanager
def span(name: str, **attributes: str | int | float | bool) -> Iterator[trace.Span]:
    with TRACER.start_as_current_span(name) as active_span:
        for key, value in attributes.items():
            active_span.set_attribute(key, value)
        yield active_span
