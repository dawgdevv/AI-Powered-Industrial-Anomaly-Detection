"""
Pipeline layer: turns the continuous ingested stream into occasional
anomaly events.

This is the file that actually implements the "streaming -> RAG" bridge
discussed earlier: 99% of readings pass through updating rolling state
and produce nothing; only the ~1% that trip a detector become an
AnomalyEvent, which is the only thing the (future) agent layer will ever
see.

Standalone runnable — no agent, no vector store, no API keys needed:

    python3 -m iot_stream.pipeline.stream_processor
"""

import asyncio
import logging
from typing import AsyncIterator

from iot_stream.ingestion.tcp_client import stream_readings
from iot_stream.incidents import DecisionPolicy, Incident, IncidentAggregator
from iot_stream.pipeline.detectors import DeviceDetectorSet
from iot_stream.schemas import AnomalyEvent

logger = logging.getLogger("iot_stream.pipeline")


async def process_stream(host: str, port: int) -> AsyncIterator[AnomalyEvent]:
    """
    Consumes the raw reading stream and yields AnomalyEvents as they're
    detected. This generator is what the agent layer will eventually
    consume — it never sees a raw SensorReading, only events.
    """
    detector_sets: dict[str, DeviceDetectorSet] = {}
    reading_count = 0
    event_count = 0

    async for reading in stream_readings(host, port):
        reading_count += 1

        if reading.device_id not in detector_sets:
            detector_sets[reading.device_id] = DeviceDetectorSet(
                max_staleness_seconds=30.0
            )

        events = detector_sets[reading.device_id].check(reading)
        for event in events:
            event_count += 1
            yield event

        if reading_count % 50 == 0:
            logger.info(f"Processed {reading_count} readings, {event_count} events so far")


async def process_incidents(host: str, port: int) -> AsyncIterator[Incident]:
    """Run the deterministic path from readings through policy decisions."""
    detector_sets: dict[str, DeviceDetectorSet] = {}
    aggregator = IncidentAggregator()
    policy = DecisionPolicy()

    async for reading in stream_readings(host, port):
        if reading.device_id not in detector_sets:
            detector_sets[reading.device_id] = DeviceDetectorSet(
                max_staleness_seconds=30.0
            )
        detectors = detector_sets[reading.device_id]
        events = detectors.check(reading)
        aggregator.resolve_quiet(reading.device_id, reading.timestamp)
        for event in events:
            incident = aggregator.aggregate(event)
            result = policy.evaluate(incident)
            yield aggregator.apply_decision(incident, result)


# ----------------------------- Manual test -----------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    async def _main():
        async for event in process_stream("localhost", 9999):
            print(
                f"\n🚨 [{event.severity.upper()}] {event.detector} on {event.device_id}\n"
                f"   {event.description}"
            )

    asyncio.run(_main())
