"""Vessel tracking endpoints + WebSocket."""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.sources.vessel_source import get_vessel_service
from app.core.freshness import FreshnessRegistry
import asyncio
import json
from datetime import datetime, timezone
from loguru import logger

router = APIRouter()


@router.get("/vessels/position")
async def get_vessel_position():
    """Return current vessel position. Clearly marks DEMO vs LIVE."""
    svc = get_vessel_service()
    pos = svc.get_position()
    freshness = FreshnessRegistry.get("ais")
    return {
        "position": pos,
        "freshness": freshness.to_dict() if freshness else None,
    }


@router.get("/vessels/track")
async def get_vessel_track(hours: int = 6):
    """Return vessel track for last N hours."""
    svc = get_vessel_service()
    track = svc.get_track(hours=min(hours, 24))
    return {
        "track": track,
        "hours": hours,
        "is_real": svc.is_live(),
        "data_mode": "live" if svc.is_live() else "demo",
    }


@router.websocket("/ws/vessel")
async def vessel_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time vessel position updates.
    Sends position update every 5 seconds.
    When AIS is live, data is real. When in demo mode, clearly labeled as DEMO.
    """
    await websocket.accept()
    logger.info(f"[ws/vessel] Client connected: {websocket.client}")

    try:
        while True:
            svc = get_vessel_service()
            pos = svc.get_position()
            freshness = FreshnessRegistry.get("ais")

            msg = {
                "type": "vessel_position",
                "position": pos,
                "freshness": freshness.to_dict() if freshness else None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await websocket.send_text(json.dumps(msg))
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        logger.info(f"[ws/vessel] Client disconnected: {websocket.client}")
    except Exception as e:
        logger.warning(f"[ws/vessel] Error: {e}")
