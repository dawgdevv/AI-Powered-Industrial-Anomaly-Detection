"""
Insgetion layer : TCP cleint for the iot mock producer 

This is the only file in the whole porject allowed  to know about scokets its jobs end moment it hands a validate 
sensor reading to whoever is consuming the stream( the pipeline layer).it knows nothing about anomalies or faults or any 
other domain specific knowledge. It just knows how to read a sensor reading from a socket and validate it.

"""

import asyncio
from csv import writer
import json 
import logging 
from typing import AsyncIterator

from iot_stream.schemas import SensorReading

logger = logging.getLogger("iot_stream.ingestion")

RECONNECT_START_BACKOFF = 1.0
RECONNECT_MAX_BACKOFF = 15.0

async def stream_readings(host:str,port:int) -> AsyncIterator[SensorReading]:
    """

    connects to the producer and yields validated sensor readings as they arrive. 
    If the connection is lost, it will attempt to reconnect with exponential backoff.

    """
    backoff = RECONNECT_START_BACKOFF

    while True:
        try:
            logger.info(f"Connecting to {host}:{port}")
            reader, writer = await asyncio.open_connection(host, port)
            logger.info("connected to ingest live stream")
            backoff = RECONNECT_START_BACKOFF  # Reset backoff after a successful connection

            async for line in reader:
                reading = _parse_line(line)
                if reading is not None:
                    yield reading
            
            logger.warning("Connection closed by the server. Attempting to reconnect...")
        
        except(ConnectionRefusedError,ConnectionResetError,OSError) as e:
            logger.error(f"Connection error: {e}. Retrying in {backoff} seconds...")


        finally:
            try:
                writer.close()
                await writer.wait_closed()
                
            except Exception as e:
                logger.error(f"Error closing connection: {e}")
        

        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, RECONNECT_MAX_BACKOFF)

def _parse_line(line:bytes) -> SensorReading:
    """
    Parses a line of bytes from the socket and returns a SensorReading object if valid.
    Returns None if the line is invalid or cannot be parsed.
    """
    try:
        data = json.loads(line.decode().strip())
        reading = SensorReading.from_dict(data)
        return reading
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.error(f"Failed to parse line: {line}. Error: {e}")
        return None


