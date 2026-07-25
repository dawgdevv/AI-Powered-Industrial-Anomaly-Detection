"""A real local OTLP HTTP collector verifies trace export without SigNoz."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import unittest

from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor


class _Collector(BaseHTTPRequestHandler):
    requests: list[tuple[str, bytes]] = []

    def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        length = int(self.headers.get("Content-Length", "0"))
        type(self).requests.append((self.path, self.rfile.read(length)))
        self.send_response(200)
        self.end_headers()

    def log_message(self, _format: str, *_args: object) -> None:
        return


class OtlpExportTests(unittest.TestCase):
    def test_span_is_exported_to_otlp_http_collector(self):
        _Collector.requests = []
        server = ThreadingHTTPServer(("127.0.0.1", 0), _Collector)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        endpoint = f"http://127.0.0.1:{server.server_port}/v1/traces"
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        try:
            with provider.get_tracer("iot_stream.test").start_as_current_span("sensor.process") as span:
                span.set_attribute("incident.id", "INC-OTLP-TEST")
            self.assertEqual(len(_Collector.requests), 1)
            path, payload = _Collector.requests[0]
            self.assertEqual(path, "/v1/traces")
            self.assertGreater(len(payload), 0)
        finally:
            provider.shutdown()
            server.shutdown()
            server.server_close()
            thread.join(timeout=1)


if __name__ == "__main__":
    unittest.main()
