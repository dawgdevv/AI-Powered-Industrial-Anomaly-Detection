"""
Fault models for sensor simulation.

The random-walk-with-fault-injection approach here is adapted from
antonsarg/iot-sensor-data-simulator (MIT License):
https://github.com/antonsarg/iot-sensor-data-simulator

That project models four realistic IoT fault modes instead of a single
"spike" anomaly, which is a more honest representation of what actually
goes wrong with real sensors:

  - ANOMALY   : sudden positive/negative spikes (e.g. a real fault event)
  - MCAR      : "missing completely at random" — dropped/null readings,
                simulating packet loss or a sensor briefly going offline
  - DUPLICATE : the same reading sent twice, simulating a flaky publisher
                retrying without deduplication
  - DRIFT     : the sensor's baseline slowly shifts over time, simulating
                gradual miscalibration (a very different failure mode from
                a spike — no single reading looks wrong, only the trend)

This module reimplements that logic (not a copy of the original file) to
fit this project's dataclass-based, dependency-free sensor model.
"""

import random
from dataclasses import dataclass, field
from typing import Optional

NO_ERROR = "no_error"
ANOMALY = "anomaly"
MCAR = "mcar"
DUPLICATE_DATA = "duplicate_data"
DRIFT = "drift"

DRIFT_APPLY_EVERY_N_ITERATIONS = 10


@dataclass
class ErrorDefinition:
    type: str = NO_ERROR
    # anomaly params
    probability_pos_anomaly: float = 0.0
    probability_neg_anomaly: float = 0.0
    pos_anomaly_range: tuple = (0.0, 0.0)
    neg_anomaly_range: tuple = (0.0, 0.0)
    # mcar params
    mcar_probability: float = 0.0
    # duplicate params
    duplicate_probability: float = 0.0
    # drift params
    drift_after_n_iterations: int = 999999
    average_drift_rate: float = 0.0
    drift_variation_range: float = 0.0


@dataclass
class RandomWalkChannel:
    """A single sensor channel (e.g. temperature) that random-walks around
    a base value and can have a fault mode layered on top."""

    base_value: float
    variation_range: float
    change_rate: float
    error: ErrorDefinition = field(default_factory=ErrorDefinition)
    rng: random.Random = field(default_factory=random.Random, repr=False)

    def __post_init__(self):
        self.previous_value = self.base_value
        self.iteration = 0
        self._drifting = False
        self._last_duplicate_iteration = -10
        self._last_record = None

    def generate(self) -> dict:
        """Returns {"value": float|None, "duplicate": bool, "fault_active": bool}"""
        step = self.rng.uniform(-self.change_rate, self.change_rate)
        value = self.previous_value + step
        value = max(self.base_value - self.variation_range,
                    min(self.base_value + self.variation_range, value))
        self.previous_value = value

        duplicate = False
        fault_active = False

        if self.error.type == ANOMALY:
            value, fault_active = self._apply_anomaly(value)
        elif self.error.type == MCAR:
            value, fault_active = self._apply_mcar(value)
        elif self.error.type == DUPLICATE_DATA:
            duplicate, fault_active = self._apply_duplicate()
        elif self.error.type == DRIFT:
            fault_active = self._apply_drift()

        self.iteration += 1
        result = {
            "value": round(value, 3) if value is not None else None,
            "duplicate": duplicate,
            "fault_active": fault_active,
        }
        self._last_record = result
        return result

    def _apply_anomaly(self, value):
        active = False
        if self.rng.random() < self.error.probability_pos_anomaly:
            value += self.rng.uniform(*self.error.pos_anomaly_range)
            active = True
        if self.rng.random() < self.error.probability_neg_anomaly:
            value -= self.rng.uniform(*self.error.neg_anomaly_range)
            active = True
        return value, active

    def _apply_mcar(self, value):
        if self.rng.random() < self.error.mcar_probability:
            return None, True
        return value, False

    def _apply_duplicate(self):
        if (self.iteration - self._last_duplicate_iteration > 2
                and self.rng.random() < self.error.duplicate_probability):
            self._last_duplicate_iteration = self.iteration
            return True, True
        return False, False

    def _apply_drift(self):
        if self._drifting or self.iteration >= self.error.drift_after_n_iterations:
            self._drifting = True
            if self.iteration % DRIFT_APPLY_EVERY_N_ITERATIONS != 0:
                return True
            deviation = self.rng.uniform(-self.error.drift_variation_range,
                                         self.error.drift_variation_range)
            self.base_value += self.error.average_drift_rate + deviation
            return True
        return False
