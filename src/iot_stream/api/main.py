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

from iot_stream.api.models import KnowledgeSearchRequest, PolicyConfig, ReviewRequest
from iot_stream.api.runtime import CONFIGURED_FLEET_SIZE, StreamRuntime
from iot_stream.incidents.models import IncidentCategory, IncidentState
from iot_stream.knowledge import RetrievalQuery, build_incident_retriever, build_knowledge_store
from iot_stream.telemetry import configure_telemetry, health_status as telemetry_health_status, shutdown_telemetry


def create_app(
    runtime: StreamRuntime | None = None, *, start_worker: bool = True
) -> FastAPI:
    live_runtime = runtime or StreamRuntime(
        host=os.getenv("IOT_STREAM_HOST", "127.0.0.1"),
        port=int(os.getenv("IOT_STREAM_PORT", "9999")),
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        configure_telemetry()
        task = asyncio.create_task(live_runtime.run()) if start_worker else None
        try:
            yield
        finally:
            if task is not None:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
            shutdown_telemetry()

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
        reading_age = None if store.last_reading_at is None else time.time() - store.last_reading_at
        stream_live = store.stream_status == "connected" and (reading_age is None or reading_age < 15)
        try:
            document_count = build_knowledge_store().count()
            knowledge = {
                "id": "knowledge",
                "name": "Chroma knowledge base",
                "state": "active" if document_count else "degraded",
                "detail": f"{document_count} indexed water-treatment records" if document_count else "No incident records indexed",
            }
        except Exception:
            knowledge = {
                "id": "knowledge",
                "name": "Chroma knowledge base",
                "state": "down",
                "detail": "The local scenario store is unavailable",
            }
        telemetry = telemetry_health_status()
        services = [
            {
                "id": "stream",
                "name": "Telemetry stream",
                "state": "active" if stream_live else ("degraded" if store.stream_status != "unavailable" else "down"),
                "detail": "Live sensor feed is flowing" if stream_live else (store.stream_error or "Waiting for the sensor feed"),
            },
            {
                "id": "detectors",
                "name": "Detector engine",
                "state": "active" if stream_live else "standby",
                "detail": "Evaluating vibration, drift, and data quality" if stream_live else "Starts when telemetry arrives",
            },
            {
                "id": "incidents",
                "name": "Incident workflow",
                "state": "active" if stream_live else "standby",
                "detail": "Grouping evidence and monitoring recovery" if stream_live else "Waiting for detector evidence",
            },
            knowledge,
            {
                "id": "agent",
                "name": "Flow Warden agent",
                "state": "active" if live_runtime.agent.model_available else "standby",
                "detail": "Mistral assessment is available" if live_runtime.agent.model_available else "Safe deterministic assessment is ready",
            },
            {
                "id": "policy",
                "name": "Runtime policy store",
                "state": "active" if live_runtime.database is not None else "standby",
                "detail": "SQLite persistence is enabled" if live_runtime.database is not None else "In-memory policy for this session",
            },
            {
                "id": "observability",
                "name": "SigNoz telemetry",
                "state": telemetry["state"],
                "detail": telemetry["detail"],
            },
        ]
        return {
            "api": "ok",
            "stream_status": store.stream_status,
            "stream_error": store.stream_error,
            "last_reading_at": store.last_reading_at,
            "uptime_seconds": round(time.time() - store.started_at, 3),
            "sensor_count": len(store.sensors),
            "configured_fleet_size": CONFIGURED_FLEET_SIZE,
            "incident_count": len(store.incidents),
            "services": services,
        }

    @app.get("/api/knowledge/health")
    async def knowledge_health() -> dict:
        try:
            store = build_knowledge_store()
            count = store.count()
        except Exception as error:
            raise HTTPException(
                status_code=503, detail=f"knowledge store unavailable: {error}"
            ) from error
        return {
            "status": "ready" if count else "empty",
            "collection": "water_treatment_incidents",
            "document_count": count,
            "persist_path": os.getenv("CHROMA_PERSIST_PATH", "data/chroma"),
        }

    @app.post("/api/knowledge/search")
    async def search_knowledge(request_body: KnowledgeSearchRequest) -> list[dict]:
        try:
            matches = build_incident_retriever().search(
                RetrievalQuery(
                    text=request_body.text,
                    equipment_type=request_body.equipment_type,
                    sensor_type=request_body.sensor_type,
                    incident_category=request_body.incident_category,
                    limit=request_body.limit,
                )
            )
        except Exception as error:
            raise HTTPException(
                status_code=503, detail=f"knowledge retrieval unavailable: {error}"
            ) from error
        return [
            {
                "incident_id": match.incident_id,
                "retrieval_text": match.retrieval_text,
                "metadata": match.metadata,
                "distance": match.distance,
            }
            for match in matches
        ]

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

    @app.post("/api/incidents/{incident_id}/review")
    async def review(incident_id: str, request_body: ReviewRequest) -> dict:
        snapshot = await live_runtime.review(incident_id, request_body)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="incident not found")
        return snapshot

    @app.get("/api/stream")
    async def stream(request: Request) -> StreamingResponse:
        queue = live_runtime.store.subscribe()

        async def event_source() -> AsyncIterator[str]:
            try:
                yield "retry: 2000\n\n"
                yield f"event: stream.connected\ndata: {json.dumps({'connected_at': time.time()})}\n\n"
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
