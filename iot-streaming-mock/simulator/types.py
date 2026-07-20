from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class SensorReading:
    device_id: str
    timestamp: float
    temperature: Optional[float]
    humidity: Optional[float]
    vibration: Optional[float]
    fault_type: str
    fault_active: bool
    duplicate: bool

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
