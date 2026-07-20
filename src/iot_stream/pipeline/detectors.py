"""
Detector strategies for the pipeline layer.

Each fault mode from the simulator needs a genuinely different detection
approach — this is the point worth making in an interview, not just an
implementation detail:

  - SPIKE (single-value anomaly): a per-reading z-score check is enough.
    You can catch it by looking at ONE reading against recent history.

  - DROPOUT (MCAR nulls): a single missing reading means nothing on its
    own — sensors occasionally miss a beat. What matters is the RATE of
    missing readings over a window. This requires state across many
    readings, not a per-reading check.

  - DRIFT: no single reading looks wrong at all. Only the slope of the
    rolling mean over a long window reveals it. This is the fault mode
    that would be invisible to a naive threshold alarm.

  - DUPLICATE: not a physical fault, but a data-quality issue (flaky
    publisher). Flagged directly from the transport-level flag rather
    than inferred statistically.

Every detector is pure and stateful only for a single device — no
knowledge of TCP, agents, or vector stores. That's what keeps this layer
testable with plain unit tests and no dependencies.
"""

from collections import deque
from typing import Optional

from iot_stream.schemas import SensorReading, AnomalyEvent

# ----------------------------- CONFIG -----------------------------
SPIKE_WINDOW = 30
SPIKE_Z_THRESHOLD = 3.0
SPIKE_MIN_ABS_DEVIATION = 0.15   # ignore z-score alone on very low-variance sensors

DROPOUT_WINDOW = 20
DROPOUT_RATE_THRESHOLD = 0.25   # >25% missing in the window = real problem

DRIFT_WINDOW = 60
DRIFT_MIN_SAMPLES = 30
DRIFT_SLOPE_THRESHOLD = 0.01    # change per reading, in sensor units
DRIFT_COOLDOWN_READINGS = 20    # re-alert on drift at most this often while still active


class SpikeDetector:
    """Per-device rolling z-score check on vibration.

    Edge-triggered: fires once when entering an anomalous state, stays
    silent while it remains anomalous, and can fire again once it's
    cleared and re-trips. This avoids alarm-flooding the same fault.
    """

    def __init__(self):
        self.history = deque(maxlen=SPIKE_WINDOW)
        self.is_outlier_last = False  # exposed so DriftDetector can skip contamination
        self._active = False

    def check(self, reading: SensorReading) -> Optional[AnomalyEvent]:
        self.is_outlier_last = False
        if reading.vibration is None:
            return None  # dropout detector's job, not this one's

        event = None
        is_anomalous = False

        if len(self.history) >= 8:
            mean = sum(self.history) / len(self.history)
            var = sum((x - mean) ** 2 for x in self.history) / len(self.history)
            std = var ** 0.5 + 1e-6
            abs_diff = abs(reading.vibration - mean)
            z = abs_diff / std

            is_anomalous = z > SPIKE_Z_THRESHOLD and abs_diff > SPIKE_MIN_ABS_DEVIATION
            if is_anomalous:
                self.is_outlier_last = True  # tell drift detector to skip this value
                if not self._active:
                    event = AnomalyEvent(
                        device_id=reading.device_id,
                        timestamp=reading.timestamp,
                        detector="spike",
                        description=(
                            f"Vibration {reading.vibration:.3f} is {z:.1f} std devs "
                            f"from the recent mean of {mean:.3f}"
                        ),
                        severity="high" if z > SPIKE_Z_THRESHOLD * 1.5 else "medium",
                        reading=reading,
                        context={"z_score": round(z, 2), "rolling_mean": round(mean, 3)},
                    )

        self._active = is_anomalous
        # Only feed non-outlier values back into the baseline history, so one
        # spike doesn't drag the rolling mean/std toward itself.
        if not self.is_outlier_last:
            self.history.append(reading.vibration)
        return event


class DropoutDetector:
    """Tracks the RATE of missing readings over a window — a single null
    means nothing, a sustained high rate means the sensor is failing.
    Edge-triggered: fires once on crossing into a high-dropout state."""

    def __init__(self):
        self.history = deque(maxlen=DROPOUT_WINDOW)
        self._active = False

    def check(self, reading: SensorReading) -> Optional[AnomalyEvent]:
        self.history.append(reading.vibration is None)

        event = None
        is_anomalous = False
        if len(self.history) >= 10:
            rate = sum(self.history) / len(self.history)
            is_anomalous = rate > DROPOUT_RATE_THRESHOLD
            if is_anomalous and not self._active:
                event = AnomalyEvent(
                    device_id=reading.device_id,
                    timestamp=reading.timestamp,
                    detector="dropout",
                    description=(
                        f"{rate:.0%} of the last {len(self.history)} readings "
                        f"are missing — sensor may be failing intermittently"
                    ),
                    severity="medium",
                    reading=reading,
                    context={"dropout_rate": round(rate, 2)},
                )
        self._active = is_anomalous
        return event


class DriftDetector:
    """Compares the rolling mean of the first half vs second half of a long
    window. Catches slow miscalibration that no single reading reveals.

    Deliberately ignores values the spike detector already flagged as
    outliers, so a single spike can't masquerade as gradual drift. Also
    rate-limited so a genuinely drifting sensor doesn't re-alert on every
    single reading while still drifting.
    """

    def __init__(self):
        self.history = deque(maxlen=DRIFT_WINDOW)
        self._readings_since_alert = DRIFT_COOLDOWN_READINGS  # allow immediate first alert

    def check(self, reading: SensorReading, skip_update: bool = False) -> Optional[AnomalyEvent]:
        if reading.vibration is not None and not skip_update:
            self.history.append(reading.vibration)

        self._readings_since_alert += 1
        event = None
        if len(self.history) >= DRIFT_MIN_SAMPLES:
            half = len(self.history) // 2
            first_half = list(self.history)[:half]
            second_half = list(self.history)[half:]
            mean_a = sum(first_half) / len(first_half)
            mean_b = sum(second_half) / len(second_half)
            slope = (mean_b - mean_a) / half

            if abs(slope) > DRIFT_SLOPE_THRESHOLD and self._readings_since_alert >= DRIFT_COOLDOWN_READINGS:
                event = AnomalyEvent(
                    device_id=reading.device_id,
                    timestamp=reading.timestamp,
                    detector="drift",
                    description=(
                        f"Baseline shifted from {mean_a:.3f} to {mean_b:.3f} "
                        f"over {len(self.history)} readings — gradual drift, not a spike"
                    ),
                    severity="low",
                    reading=reading,
                    context={"mean_before": round(mean_a, 3), "mean_after": round(mean_b, 3)},
                )
                self._readings_since_alert = 0
        return event


class DuplicateDetector:
    """Flags transport-level duplicates directly — a data-quality issue,
    not a physical fault, so it's kept structurally separate."""

    def check(self, reading: SensorReading) -> Optional[AnomalyEvent]:
        if reading.duplicate:
            return AnomalyEvent(
                device_id=reading.device_id,
                timestamp=reading.timestamp,
                detector="duplicate",
                description="Duplicate reading received — possible flaky publisher retry",
                severity="low",
                reading=reading,
            )
        return None


class DeviceDetectorSet:
    """Bundles all four detectors for one device."""

    def __init__(self):
        self.spike = SpikeDetector()
        self.dropout = DropoutDetector()
        self.drift = DriftDetector()
        self.duplicate = DuplicateDetector()

    def check(self, reading: SensorReading) -> list[AnomalyEvent]:
        events = []

        spike_event = self.spike.check(reading)
        if spike_event is not None:
            events.append(spike_event)

        # Drift must run AFTER spike, using spike's outlier flag, so a
        # single spike can't be misread as gradual baseline drift.
        drift_event = self.drift.check(reading, skip_update=self.spike.is_outlier_last)
        if drift_event is not None:
            events.append(drift_event)

        for detector in (self.dropout, self.duplicate):
            result = detector.check(reading)
            if result is not None:
                events.append(result)

        return events