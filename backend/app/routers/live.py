"""
POLAR-AI Live Data Router
=========================
WebSocket /ws/live  — broadcasts typed events to all connected clients
GET /api/live/status — current run state + next scheduled update
GET /api/live/last-update — most recent completed run summary
GET /api/live/changes — what changed in the last hour
POST /api/live/trigger — run an immediate update now
GET /api/live/history — last N update runs
"""
from __future__ import annotations
import asyncio
import json
from datetime import datetime, timezone, timedelta
from typing import Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from loguru import logger

from app.config import settings

router = APIRouter()

# ── WebSocket connection manager ───────────────────────────────────────────────

class LiveConnectionManager:
    """
    Manages all /ws/live WebSocket connections.
    Provides broadcast capability used by the hourly update orchestrator.
    """
    def __init__(self):
        self._connections: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.add(ws)
        logger.info(f"[ws/live] Client connected. Total: {len(self._connections)}")

    def disconnect(self, ws: WebSocket):
        self._connections.discard(ws)
        logger.info(f"[ws/live] Client disconnected. Total: {len(self._connections)}")

    async def broadcast(self, payload: dict):
        """Send an event to all connected clients."""
        if not self._connections:
            return
        msg = json.dumps(payload, default=str)
        dead = set()
        for ws in self._connections.copy():
            try:
                await ws.send_text(msg)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self._connections.discard(ws)

    @property
    def connection_count(self) -> int:
        return len(self._connections)


# Global manager instance — imported by main.py to wire into hourly_update_service
manager = LiveConnectionManager()


@router.websocket("/ws/live")
async def live_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time data events.

    Events sent to clients:
      DATA_REFRESH_COMPLETE   — hourly update finished
      SATELLITE_UPDATED       — new satellite product found
      SEA_ICE_UPDATED         — new sea ice observation
      ICEBERGS_UPDATED        — new iceberg data
      WEATHER_UPDATED         — new weather grid
      OCEAN_UPDATED           — new ocean grid
      VESSEL_UPDATED          — new AIS position
      RISK_UPDATED            — risk recalculated
      ROUTE_UPDATED           — route re-evaluated
      DATA_SOURCE_UPDATED     — a source changed status
      PING                    — keepalive (every 25s)
    """
    await manager.connect(websocket)

    # Send immediate welcome + current system state
    from app.core.freshness import FreshnessRegistry
    from app.services.hourly_update_service import get_current_run, get_next_run_at

    try:
        next_run = get_next_run_at()
        welcome = {
            "event": "CONNECTED",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data_mode": settings.effective_data_mode,
            "update_interval_minutes": settings.UPDATE_INTERVAL_MINUTES,
            "next_update_at": next_run.isoformat() if next_run else None,
            "sources": FreshnessRegistry.summary()["sources"],
            "ws_connections": manager.connection_count,
            "message": (
                "Connected to POLAR-AI live data stream. "
                f"Data updates every {settings.UPDATE_INTERVAL_MINUTES} minutes."
            ),
        }
        await websocket.send_text(json.dumps(welcome, default=str))
    except Exception as e:
        logger.warning(f"[ws/live] Welcome send failed: {e}")

    # Keepalive + listen for client messages
    try:
        while True:
            try:
                # Wait for either a client message or timeout (25s ping cycle)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=25.0)
                # Echo back subscription/ping from client
                try:
                    msg = json.loads(data)
                    if msg.get("type") == "ping":
                        await websocket.send_text(json.dumps({
                            "event": "PONG",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }))
                except Exception:
                    pass
            except asyncio.TimeoutError:
                # Send keepalive ping
                try:
                    await websocket.send_text(json.dumps({
                        "event": "PING",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }))
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug(f"[ws/live] Connection ended: {e}")
    finally:
        manager.disconnect(websocket)


# ── REST endpoints ─────────────────────────────────────────────────────────────

@router.get("/live/status")
async def get_live_status():
    """
    Current data engine status:
    - Is the scheduler running?
    - When did the last update run?
    - When is the next update?
    - How many WebSocket clients connected?
    - Status of all data sources.
    """
    from app.core.freshness import FreshnessRegistry
    from app.services.hourly_update_service import (
        get_current_run, get_next_run_at, get_run_history
    )
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from app.ingestion.scheduler import _scheduler
        scheduler_running = _scheduler is not None and _scheduler.running
    except Exception:
        scheduler_running = False

    current_run = get_current_run()
    next_run = get_next_run_at()
    history = get_run_history(limit=5)

    now = datetime.now(timezone.utc)
    seconds_to_next = None
    if next_run:
        seconds_to_next = max(0, (next_run - now).total_seconds())

    return {
        "data_engine": "running" if scheduler_running else "stopped",
        "data_mode": settings.effective_data_mode,
        "update_interval_minutes": settings.UPDATE_INTERVAL_MINUTES,
        "next_update_at": next_run.isoformat() if next_run else None,
        "seconds_to_next_update": round(seconds_to_next, 0) if seconds_to_next is not None else None,
        "ws_clients_connected": manager.connection_count,
        "current_run": {
            "status": current_run.get("status") if current_run else None,
            "run_number": current_run.get("run_number") if current_run else 0,
            "started_at": current_run.get("started_at") if current_run else None,
        },
        "last_completed_run_number": history[-1].get("run_number") if history else 0,
        "total_runs": len(history),
        "sources": FreshnessRegistry.summary(),
        "timestamp": now.isoformat(),
        "credentials": {
            "copernicus_satellite": settings.has_copernicus,
            "nsidc_sea_ice": True,          # free, no creds needed
            "nic_icebergs": True,           # free
            "open_meteo_weather": True,     # free
            "open_meteo_ocean": True,       # free
            "ais_vessel": settings.has_ais,
            "llm": settings.has_llm,
            "llm_provider": settings.llm_provider,
        },
    }


@router.get("/live/last-update")
async def get_last_update():
    """Full detail of the most recent completed update run."""
    from app.services.hourly_update_service import get_run_history, get_next_run_at
    history = get_run_history(limit=1)
    if not history:
        return {
            "status": "no_runs_yet",
            "message": "No update runs completed yet. First run happens at startup.",
            "next_run_at": get_next_run_at().isoformat() if get_next_run_at() else None,
        }
    return history[-1]


@router.get("/live/changes")
async def get_live_changes():
    """What changed in the most recent update vs the previous one."""
    from app.services.hourly_update_service import compute_changes
    return compute_changes()


@router.get("/live/history")
async def get_live_history(limit: int = 24):
    """Last N update run summaries (max 48)."""
    from app.services.hourly_update_service import get_run_history
    limit = min(limit, 48)
    return {
        "runs": get_run_history(limit=limit),
        "count": limit,
    }


@router.post("/live/trigger")
async def trigger_update():
    """
    Manually trigger an immediate data update.
    Useful for demos and testing.
    """
    from app.services.hourly_update_service import run_hourly_update
    logger.info("[live] Manual update triggered via API")
    # Run in background — don't block the HTTP response
    asyncio.create_task(run_hourly_update(triggered_by="manual"))
    return {
        "status": "triggered",
        "message": "Hourly update started. Monitor /api/live/status for progress.",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
