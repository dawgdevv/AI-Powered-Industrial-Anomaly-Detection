"""FastAPI routes for live sensor, incident, and policy operations."""

from __future__ import annotations

import asyncio
import json
import os
import time
from contextlib import asynccontextmanager, suppress
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from iot_stream.api.models import PolicyConfig
from iot_stream.api.runtime import CONFIGURED_FLEET_SIZE, StreamRuntime
from iot_stream.incidents.models import IncidentCategory, IncidentState


def create_app(
    runtime: StreamRuntime | None = None, *, start_worker: bool = True
) -> FastAPI:
    live_runtime = runtime or StreamRuntime(
        host=os.getenv("IOT_STREAM_HOST", "127.0.0.1"),
        port=int(os.getenv("IOT_STREAM_PORT", "9999")),
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        task = asyncio.create_task(live_runtime.run()) if start_worker else None
        try:
            yield
        finally:
            if task is not None:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    app = FastAPI(
        title="IoT Anomaly Control API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.runtime = live_runtime
    origins = os.getenv("DASHBOARD_ORIGINS", "http://localhost:5173").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in origins if origin.strip()],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["Content-Type"],
    )

    @app.get("/api/health")
    async def health() -> dict:
        store = live_runtime.store
        return {
            "api": "ok",
            "stream_status": store.stream_status,
            "stream_error": store.stream_error,
            "last_reading_at": store.last_reading_at,
            "uptime_seconds": round(time.time() - store.started_at, 3),
            "sensor_count": len(store.sensors),
            "configured_fleet_size": CONFIGURED_FLEET_SIZE,
            "incident_count": len(store.incidents),
        }

    @app.get("/api/sensors")
    async def sensors() -> list[dict]:
        return live_runtime.store.sensor_snapshots()

    @app.get("/api/sensors/{device_id}")
    async def sensor(device_id: str) -> dict:
        snapshot = live_runtime.store.sensor_snapshot(device_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="sensor not found")
        return snapshot

    @app.get("/api/incidents")
    async def incidents(
        state: IncidentState | None = None,
        category: IncidentCategory | None = None,
    ) -> list[dict]:
        snapshots = live_runtime.store.incident_snapshots()
        return [
            incident
            for incident in snapshots
            if (state is None or incident["state"] == state.value)
            and (category is None or incident["category"] == category.value)
        ]

    @app.get("/api/incidents/{incident_id}")
    async def incident(incident_id: str) -> dict:
        stored = live_runtime.store.incidents.get(incident_id)
        if stored is None:
            raise HTTPException(status_code=404, detail="incident not found")
        return live_runtime.store.incident_snapshot(stored)

    @app.get("/api/activity")
    async def activity(limit: int = Query(default=50, ge=1, le=120)) -> list[dict]:
        return list(live_runtime.store.activity)[:limit]

    @app.get("/api/policy")
    async def get_policy() -> dict:
        return live_runtime.store.policy_config.model_dump()

    @app.put("/api/policy")
    async def update_policy(config: PolicyConfig) -> dict:
        return await live_runtime.update_policy(config)

    @app.post("/api/incidents/{incident_id}/acknowledge")
    async def acknowledge(incident_id: str) -> dict:
        snapshot = await live_runtime.acknowledge(incident_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="incident not found")
        return snapshot

    @app.post("/api/incidents/{incident_id}/resolve")
    async def resolve(incident_id: str) -> dict:
        snapshot = await live_runtime.resolve(incident_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="incident not found")
        return snapshot

    @app.get("/api/stream")
    async def stream(request: Request) -> StreamingResponse:
        queue = live_runtime.store.subscribe()

        async def event_source() -> AsyncIterator[str]:
            try:
                yield "retry: 2000\n\n"
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        message = await asyncio.wait_for(queue.get(), timeout=15.0)
                    except TimeoutError:
                        yield ": keep-alive\n\n"
                        continue
                    payload = json.dumps(
                        message["data"], separators=(",", ":"), allow_nan=False
                    )
                    yield (
                        f"id: {message['id']}\n"
                        f"event: {message['event']}\n"
                        f"data: {payload}\n\n"
                    )
            finally:
                live_runtime.store.unsubscribe(queue)

        return StreamingResponse(
            event_source(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    return app


app = create_app()
