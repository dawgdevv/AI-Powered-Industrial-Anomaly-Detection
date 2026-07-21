from iot_stream.schemas import AnomalyEvent, SensorReading


def reading(
    sequence: int = 1,
    *,
    device_id: str = "sensor-1",
    vibration: float | None = 0.2,
    timestamp: float | None = None,
    event_id: str | None = None,
) -> SensorReading:
    return SensorReading(
        event_id=event_id or f"{device_id}-evt-{sequence:06d}",
        sequence_number=sequence,
        device_id=device_id,
        equipment_type="centrifugal_pump",
        sensor_type="vibration",
        unit="mm/s",
        timestamp=float(sequence if timestamp is None else timestamp),
        temperature=22.0,
        humidity=50.0,
        vibration=vibration,
    )


def anomaly(
    detector: str,
    sequence: int = 1,
    *,
    device_id: str = "sensor-1",
    severity: str = "medium",
    vibration: float | None = 0.8,
) -> AnomalyEvent:
    sensor_reading = reading(
        sequence, device_id=device_id, vibration=vibration
    )
    return AnomalyEvent(
        device_id=device_id,
        timestamp=sensor_reading.timestamp,
        detector=detector,
        description=f"{detector} detected",
        severity=severity,
        reading=sensor_reading,
    )
