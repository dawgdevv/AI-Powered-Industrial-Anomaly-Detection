import json
import math
import unittest
from unittest.mock import AsyncMock, patch

from iot_stream.ingestion.tcp_client import parse_reading_line, stream_readings
from iot_stream.schemas import SensorReading, SensorValidationError
from test.helpers import reading


class SensorSchemaTests(unittest.TestCase):
    def test_round_trip_valid_reading(self):
        original = reading()
        parsed = SensorReading.from_dict(original.to_dict())
        self.assertEqual(parsed, original)

    def test_reports_all_missing_required_fields(self):
        with self.assertRaises(SensorValidationError) as caught:
            SensorReading.from_dict({"device_id": "sensor-1"})
        self.assertIn("missing_event_id", caught.exception.reason_codes)
        self.assertIn("missing_vibration", caught.exception.reason_codes)

    def test_rejects_invalid_types_and_non_finite_values(self):
        payload = reading().to_dict()
        payload.update(sequence_number=True, temperature=math.inf)
        with self.assertRaises(SensorValidationError) as caught:
            SensorReading.from_dict(payload)
        self.assertIn("invalid_sequence_number", caught.exception.reason_codes)
        self.assertIn("invalid_temperature", caught.exception.reason_codes)

    def test_nullable_sensor_channels_remain_valid(self):
        payload = reading().to_dict()
        payload.update(humidity=None, vibration=None)
        parsed = SensorReading.from_dict(payload)
        self.assertIsNone(parsed.humidity)
        self.assertIsNone(parsed.vibration)

    def test_older_payload_gets_safe_asset_metadata_fallbacks(self):
        payload = reading().to_dict()
        payload.pop("asset_id")
        payload.pop("equipment_name")
        payload.pop("area")
        parsed = SensorReading.from_dict(payload)
        self.assertEqual(parsed.asset_id, "sensor-1")
        self.assertEqual(parsed.equipment_name, "Centrifugal Pump")
        self.assertEqual(parsed.area, "Unassigned area")


class IngestionParsingTests(unittest.TestCase):
    def test_parses_json_line(self):
        payload = json.dumps(reading().to_dict()).encode()
        self.assertEqual(parse_reading_line(payload), reading())

    def test_malformed_json_has_structured_reason(self):
        with self.assertRaises(SensorValidationError) as caught:
            parse_reading_line(b"{not json}\n")
        self.assertEqual(caught.exception.reason_codes, ("invalid_json",))

    def test_invalid_utf8_has_structured_reason(self):
        with self.assertRaises(SensorValidationError) as caught:
            parse_reading_line(b"\xff")
        self.assertEqual(caught.exception.reason_codes, ("invalid_utf8",))


class _OneLineReader:
    def __init__(self, line):
        self.line = line

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.line is None:
            raise StopAsyncIteration
        line, self.line = self.line, None
        return line


class _Writer:
    def close(self):
        pass

    async def wait_closed(self):
        pass


class ReconnectTests(unittest.IsolatedAsyncioTestCase):
    async def test_reconnects_after_connection_refusal(self):
        line = json.dumps(reading().to_dict()).encode() + b"\n"
        open_connection = AsyncMock(
            side_effect=[ConnectionRefusedError(), (_OneLineReader(line), _Writer())]
        )
        sleep = AsyncMock()
        with patch("asyncio.open_connection", open_connection), patch(
            "asyncio.sleep", sleep
        ):
            stream = stream_readings("localhost", 9999)
            self.assertEqual(await anext(stream), reading())
            await stream.aclose()
        self.assertEqual(open_connection.await_count, 2)
        sleep.assert_awaited_once_with(1.0)


if __name__ == "__main__":
    unittest.main()
