"""Shared, validated data contracts for the streaming application."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import isfinite
from typing import Any, Mapping


REQUIRED_READING_FIELDS = (
    "event_id",
    "sequence_number",
    "device_id",
    "equipment_type",
    "sensor_type",
    "unit",
    "timestamp",
    "temperature",
    "humidity",
    "vibration",
)


class SensorValidationError(ValueError):
    """Raised when an input payload cannot become a valid sensor reading."""

    def __init__(self, reason_codes: list[str]):
        self.reason_codes = tuple(dict.fromkeys(reason_codes))
        super().__init__(", ".join(self.reason_codes))


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


@dataclass(frozen=True)
class SensorReading:
    event_id: str
    sequence_number: int
    device_id: str
    equipment_type: str
    sensor_type: str
    unit: str
    timestamp: float
    temperature: float
    humidity: float | None
    vibration: float | None
    asset_id: str = ""
    equipment_name: str = ""
    area: str = ""
    fault_type: str | None = None
    fault_active: bool = False
    duplicate: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SensorReading":
        if not isinstance(data, Mapping):
            raise SensorValidationError(["payload_not_object"])

        reasons = [
            f"missing_{name}" for name in REQUIRED_READING_FIELDS if name not in data
        ]

        for name in (
            "event_id",
            "device_id",
            "equipment_type",
            "sensor_type",
            "unit",
            "asset_id",
            "equipment_name",
            "area",
        ):
            value = data.get(name)
            if name in data and (not isinstance(value, str) or not value.strip()):
                reasons.append(f"invalid_{name}")

        sequence = data.get("sequence_number")
        if "sequence_number" in data and (
            not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 0
        ):
            reasons.append("invalid_sequence_number")

        for name in ("timestamp", "temperature"):
            value = data.get(name)
            if name in data and (not _is_number(value) or not isfinite(float(value))):
                reasons.append(f"invalid_{name}")

        for name in ("humidity", "vibration"):
            value = data.get(name)
            if name in data and value is not None and (
                not _is_number(value) or not isfinite(float(value))
            ):
                reasons.append(f"invalid_{name}")

        fault_type = data.get("fault_type")
        if fault_type is not None and not isinstance(fault_type, str):
            reasons.append("invalid_fault_type")
        for name in ("fault_active", "duplicate"):
            if name in data and not isinstance(data[name], bool):
                reasons.append(f"invalid_{name}")

        if reasons:
            raise SensorValidationError(reasons)

        return cls(
            event_id=data["event_id"].strip(),
            sequence_number=data["sequence_number"],
            device_id=data["device_id"].strip(),
            equipment_type=data["equipment_type"].strip(),
            sensor_type=data["sensor_type"].strip(),
            unit=data["unit"].strip(),
            timestamp=float(data["timestamp"]),
            temperature=float(data["temperature"]),
            humidity=None if data["humidity"] is None else float(data["humidity"]),
            vibration=None if data["vibration"] is None else float(data["vibration"]),
            asset_id=data.get("asset_id", data["device_id"]).strip(),
            equipment_name=data.get(
                "equipment_name", data["equipment_type"].replace("_", " ").title()
            ).strip(),
            area=data.get("area", "Unassigned area").strip(),
            fault_type=fault_type,
            fault_active=data.get("fault_active", False),
            duplicate=data.get("duplicate", False),
        )


@dataclass(frozen=True)
class AnomalyEvent:
    device_id: str
    timestamp: float
    detector: str
    description: str
    severity: str
    reading: SensorReading
    context: dict[str, Any] = field(default_factory=dict)
