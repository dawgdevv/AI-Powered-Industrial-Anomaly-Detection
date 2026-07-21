"""
Insgetion layer : TCP cleint for the iot mock producer 

This is the only file in the whole porject allowed  to know about scokets its jobs end moment it hands a validate 
sensor reading to whoever is consuming the stream( the pipeline layer).it knows nothing about anomalies or faults or any 
other domain specific knowledge. It just knows how to read a sensor reading from a socket and validate it.

"""

import asyncio
import inspect
import json
import logging
from collections.abc import Awaitable, Callable
from typing import AsyncIterator

from iot_stream.schemas import SensorReading, SensorValidationError

logger = logging.getLogger("iot_stream.ingestion")

RECONNECT_START_BACKOFF = 1.0
RECONNECT_MAX_BACKOFF = 15.0

StatusCallback = Callable[[str, str | None], Awaitable[None] | None]


async def _notify_status(
    callback: StatusCallback | None, status: str, error: str | None = None
) -> None:
    if callback is None:
        return
    try:
        result = callback(status, error)
        if inspect.isawaitable(result):
            await result
    except Exception:
        logger.exception("Stream status callback failed")


async def stream_readings(
    host: str,
    port: int,
    on_status: StatusCallback | None = None,
) -> AsyncIterator[SensorReading]:
    """

    connects to the producer and yields validated sensor readings as they arrive. 
    If the connection is lost, it will attempt to reconnect with exponential backoff.

    """
    backoff = RECONNECT_START_BACKOFF

    while True:
        writer = None
        try:
            await _notify_status(on_status, "connecting")
            logger.info(f"Connecting to {host}:{port}")
            reader, writer = await asyncio.open_connection(host, port)
            logger.info("connected to ingest live stream")
            await _notify_status(on_status, "connected")
            backoff = RECONNECT_START_BACKOFF  # Reset backoff after a successful connection

            async for line in reader:
                try:
                    yield parse_reading_line(line)
                except SensorValidationError as exc:
                    logger.warning(
                        "Rejected sensor payload",
                        extra={"validation_reason_codes": exc.reason_codes},
                    )
            
            logger.warning("Connection closed by the server. Attempting to reconnect...")
            await _notify_status(on_status, "reconnecting", "producer closed connection")
        
        except(ConnectionRefusedError,ConnectionResetError,OSError) as e:
            logger.error(f"Connection error: {e}. Retrying in {backoff} seconds...")
            await _notify_status(on_status, "reconnecting", str(e))


        finally:
            try:
                if writer is not None:
                    writer.close()
                    await writer.wait_closed()
                
            except Exception as e:
                logger.error(f"Error closing connection: {e}")
        

        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, RECONNECT_MAX_BACKOFF)

def parse_reading_line(line: bytes) -> SensorReading:
    """Parse one JSON line or raise a structured validation error."""
    try:
        data = json.loads(line.decode("utf-8").strip())
    except UnicodeDecodeError as exc:
        raise SensorValidationError(["invalid_utf8"]) from exc
    except json.JSONDecodeError as exc:
        raise SensorValidationError(["invalid_json"]) from exc
    return SensorReading.from_dict(data)


def _parse_line(line:bytes) -> SensorReading | None:
    """
    Parses a line of bytes from the socket and returns a SensorReading object if valid.
    Returns None if the line is invalid or cannot be parsed.
    """
    try:
        return parse_reading_line(line)
    except SensorValidationError as exc:
        logger.error("Failed to parse sensor line: %s", ",".join(exc.reason_codes))
        return None
