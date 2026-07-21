import unittest

from iot_stream.pipeline.quality import TransportQualityDetector
from test.helpers import reading


class TransportQualityTests(unittest.TestCase):
    def test_duplicate_uses_event_id_not_ground_truth_flag(self):
        detector = TransportQualityDetector()
        first = reading(1, event_id="same-id")
        second = reading(2, event_id="same-id")
        detector.check(first)
        events = detector.check(second)
        self.assertEqual({event.detector for event in events}, {"duplicate_event"})

    def test_detects_sequence_gap(self):
        detector = TransportQualityDetector()
        detector.check(reading(3))
        events = detector.check(reading(6))
        self.assertIn("sequence_gap", {event.detector for event in events})

    def test_detects_stale_and_regressing_timestamp(self):
        detector = TransportQualityDetector(max_staleness_seconds=5.0)
        detector.check(reading(1, timestamp=100.0), received_at=101.0)
        events = detector.check(reading(2, timestamp=90.0), received_at=110.0)
        names = {event.detector for event in events}
        self.assertIn("stale_reading", names)
        self.assertIn("timestamp_regression", names)


if __name__ == "__main__":
    unittest.main()
