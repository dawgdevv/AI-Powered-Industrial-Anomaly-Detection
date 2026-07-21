from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class SensorReading:
    event_id: str
    sequence_number: int
    device_id: str
    equipment_type: str
    sensor_type: str
    unit: str
    timestamp: float
    temperature: float
    humidity: Optional[float]
    vibration: Optional[float]
    fault_type: Optional[str] = None
    fault_active: bool = False
    duplicate: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "SensorReading":
        return cls(**data)


@dataclass
class SimulatorConfig:
    host: str = "0.0.0.0"
    port: int = 9999
    num_devices: int = 4
    emit_interval: float = 0.5
    seed: Optional[int] = None
    scenario: str = "random"
