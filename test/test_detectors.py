import unittest

from iot_stream.pipeline.detectors import (
    DriftDetector,
    DropoutDetector,
    SpikeDetector,
)
from test.helpers import reading


class DetectorTests(unittest.TestCase):
    def test_spike_is_edge_triggered(self):
        detector = SpikeDetector()
        for sequence in range(1, 11):
            self.assertIsNone(detector.check(reading(sequence, vibration=0.2)))
        event = detector.check(reading(11, vibration=1.2))
        self.assertIsNotNone(event)
        self.assertEqual(event.detector, "spike")
        self.assertIsNone(detector.check(reading(12, vibration=1.1)))

    def test_drift_detects_smooth_baseline_shift(self):
        detector = DriftDetector()
        event = None
        for sequence in range(1, 40):
            event = detector.check(reading(sequence, vibration=0.2 + 0.02 * sequence)) or event
        self.assertIsNotNone(event)
        self.assertEqual(event.detector, "drift")

    def test_dropout_requires_sustained_missing_rate(self):
        detector = DropoutDetector()
        event = None
        values = [0.2] * 7 + [None] * 3
        for sequence, value in enumerate(values, 1):
            event = detector.check(reading(sequence, vibration=value)) or event
        self.assertIsNotNone(event)
        self.assertEqual(event.detector, "dropout")
        self.assertGreater(event.context["dropout_rate"], 0.25)


if __name__ == "__main__":
    unittest.main()
