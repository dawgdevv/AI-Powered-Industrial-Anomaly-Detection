"""
Shared schemas for the IoT stream application.

Every layer (ingestion,pipeline,agent) import this instead of redefining the shape of a sensor reading.


"""

from dataclasses import dataclass,field
from typing import Optional


@dataclass
class SensorReading:
    device_id:str
    timestamp:float
    temperature:float
    humidity:Optional[float]
    vibration:Optional[float]
    fault_type:str
    fault_active:bool
    duplicate:bool

    @classmethod
    def from_dict(cls,data:dict) -> "SensorReading":
        return cls(
            device_id=data.get("device_id"),
            timestamp=data.get("timestamp"),
            temperature=data.get("temperature"),
            humidity=data.get("humidity"),
            vibration=data.get("vibration"),
            fault_type=data.get("fault_type"),
            fault_active=data.get("fault_active"),
            duplicate=data.get("duplicate",False)
        )

@dataclass
class AnomalyEvent:
    """
    Represents an anomaly event detected in the sensor data.    
    """
    device_id:str
    timestamp:float
    detector:str
    description:str
    severity:str
    reading:SensorReading
    context: dict = field(default_factory=dict)