"""
POLAR-AI Vessels Router — full multi-vessel API
"""
from __future__ import annotations
import asyncio
import json
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Query, HTTPException, WebSocket, WebSocketDisconnect
from loguru import logger

from app.services.ais.ais_manager import get_registry, ensure_aisstream_running
from app.core.freshness import FreshnessRegistry
from app.config import settings
from app.core.live_gate import allow_demo_fallback

router = APIRouter()


# ── REST endpoints ─────────────────────────────────────────────────────────────

@router.get("/vessels")
async def list_vessels(
    q: str = Query(default="", description="Search by name, MMSI, or IMO"),
    limit: int = Query(default=50, ge=1, le=200),
):
    """
    List / search all currently tracked vessels.
    Returns vessels in the Antarctic region visible from AIS.
    """
    registry = get_registry()
    freshness = FreshnessRegistry.get("ais")

    if not settings.has_ais:
        return {
            "status": "NOT_CONFIGURED",
            "vessels": [],
            "total": 0,
            "message": "AIS not configured. Set AIS_PROVIDER and AIS_API_KEY.",
            "freshness": freshness.to_dict() if freshness else None,
        }

    vessels = registry.search(query=q, limit=limit)
    active = registry.active_mmsi

    return {
        "vessels": vessels,
        "total": len(vessels),
        "active_mmsi": active,
        "freshness": freshness.to_dict() if freshness else None,
        "data_mode": "live",
    }


@router.get("/vessels/active")
async def get_active_vessel():
    """Return the currently active (globally selected) vessel."""
    registry = get_registry()
    vessel = registry.get_active_vessel()
    freshness = FreshnessRegistry.get("ais")

    if not vessel:
        if not settings.has_ais:
            return {
                "status": "AIS_NOT_CONFIGURED",
                "vessel": None,
                "message": "Set AIS_PROVIDER and AIS_API_KEY to enable vessel tracking.",
                "setup": {
                    "aisstream": "Register at https://aisstream.io/ — free tier available",
                    "barentswatch": "Register at https://www.barentswatch.no/bwapi/",
                },
            }
        return {
            "status": "NO_VESSEL",
            "vessel": None,
            "message": "No vessel selected. Use POST /api/vessels/{mmsi}/select to choose a vessel.",
            "freshness": freshness.to_dict() if freshness else None,
        }

    return {
        "status": "ok",
        "vessel": vessel,
        "freshness": freshness.to_dict() if freshness else None,
        "data_mode": "live",
    }


@router.post("/vessels/{mmsi}/select")
async def select_vessel(mmsi: str):
    """
    Set the globally active vessel.
    All pages will immediately reflect this selection via WebSocket broadcast.
    """
    registry = get_registry()
    success = registry.set_active_vessel(mmsi)

    if not success:
        # Vessel not in registry yet — still store the selection
        # (it may arrive in the stream soon)
        registry._active_mmsi = mmsi
        return {
            "status": "pending",
            "mmsi": mmsi,
            "message": "Vessel MMSI set as active. Waiting for AIS position data.",
        }

    vessel = registry.get_vessel(mmsi)

    # Broadcast the selection change to all connected frontends
    from app.routers.live import manager as live_manager
    try:
        await live_manager.broadcast({
            "event": "ACTIVE_VESSEL_CHANGED",
            "mmsi": mmsi,
            "vessel": vessel,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass

    return {
        "status": "ok",
        "mmsi": mmsi,
        "vessel": vessel,
        "message": f"Active vessel changed to {vessel.get('name', mmsi) if vessel else mmsi}",
    }


@router.get("/vessels/{mmsi}")
async def get_vessel(mmsi: str):
    """Get details for a specific vessel by MMSI."""
    registry = get_registry()
    vessel = registry.get_vessel(mmsi)
    if not vessel:
        raise HTTPException(status_code=404, detail=f"Vessel MMSI '{mmsi}' not found")
    freshness = FreshnessRegistry.get("ais")
    return {
        "vessel": vessel,
        "freshness": freshness.to_dict() if freshness else None,
    }


@router.get("/vessels/{mmsi}/position")
async def get_vessel_position(mmsi: str):
    """Latest position for a specific vessel."""
    registry = get_registry()
    vessel = registry.get_vessel(mmsi)
    if not vessel:
        raise HTTPException(status_code=404, detail=f"Vessel MMSI '{mmsi}' not found")
    return {"position": vessel, "data_mode": "live"}


@router.get("/vessels/{mmsi}/track")
async def get_vessel_track(
    mmsi: str,
    hours: float = Query(default=6.0, ge=0.5, le=720),
):
    """
    Position history for a specific vessel.
    Returns only points that actually exist in the in-memory track store.
    """
    registry = get_registry()
    if mmsi not in registry._vessels:
        raise HTTPException(status_code=404, detail=f"Vessel MMSI '{mmsi}' not found")

    track = registry.get_track(mmsi, hours=hours)
    return {
        "mmsi": mmsi,
        "track": track,
        "point_count": len(track),
        "hours": hours,
        "is_real": True,
        "data_mode": "live",
        "note": None if track else "No track history for this vessel yet.",
    }


@router.get("/vessels/{mmsi}/risk")
async def get_vessel_risk(mmsi: str):
    """Calculate navigation risk for a specific vessel's current position."""
    registry = get_registry()
    vessel = registry.get_vessel(mmsi)
    if not vessel:
        raise HTTPException(status_code=404, detail=f"Vessel '{mmsi}' not found")

    lat = vessel.get("latitude")
    lon = vessel.get("longitude")
    if lat is None or lon is None:
        return {"status": "NO_POSITION", "message": "Vessel has no valid position."}

    from app.services.risk_service import calculate_risk
    from app.schemas.routes import RiskCalculateRequest
    req = RiskCalculateRequest(latitude=lat, longitude=lon, radius_km=100.0)
    risk = calculate_risk(req)
    risk["vessel_mmsi"] = mmsi
    risk["vessel_name"] = vessel.get("name", mmsi)
    return risk


@router.get("/vessels/{mmsi}/nearby-hazards")
async def get_nearby_hazards(
    mmsi: str,
    radius_km: float = Query(default=200.0, ge=10, le=1000),
):
    """
    Find nearby icebergs, sea-ice zones, and weather hazards
    around a specific vessel's current position.
    """
    registry = get_registry()
    vessel = registry.get_vessel(mmsi)
    if not vessel:
        raise HTTPException(status_code=404, detail=f"Vessel '{mmsi}' not found")

    lat = vessel.get("latitude")
    lon = vessel.get("longitude")
    if lat is None or lon is None:
        return {"status": "NO_POSITION"}

    # Nearby icebergs
    from app.services.iceberg_service import list_icebergs
    from app.services.demo_service import haversine_km

    all_icebergs_resp = list_icebergs()
    all_icebergs = all_icebergs_resp.get("icebergs", []) if isinstance(all_icebergs_resp, dict) else []

    nearby_icebergs = []
    for ib in all_icebergs:
        if ib.get("latitude") is None:
            continue
        dist = haversine_km(lat, lon, ib["latitude"], ib["longitude"])
        if dist <= radius_km:
            ib_copy = dict(ib)
            ib_copy["distance_km"] = round(dist, 1)
            ib_copy["bearing_deg"] = round(
                _bearing(lat, lon, ib["latitude"], ib["longitude"]), 1)
            nearby_icebergs.append(ib_copy)

    nearby_icebergs.sort(key=lambda x: x["distance_km"])

    # Local sea ice
    from app.services.sea_ice_service import get_current_sea_ice
    ice = get_current_sea_ice("low")
    local_ice = None
    if isinstance(ice, dict) and "grid_points" in ice:
        grid = ice["grid_points"]
        if grid:
            nearest_cell = min(
                grid,
                key=lambda p: haversine_km(lat, lon, p["latitude"], p["longitude"])
            )
            local_ice = {
                "concentration": nearest_cell["concentration"],
                "category": nearest_cell["ice_category"],
                "lat": nearest_cell["latitude"],
                "lon": nearest_cell["longitude"],
            }

    # Weather at vessel position
    from app.services.weather_service import get_nearest as get_nearest_wx
    weather_at_vessel = get_nearest_wx(lat, lon)

    return {
        "vessel_mmsi": mmsi,
        "vessel_name": vessel.get("name", mmsi),
        "position": {"latitude": lat, "longitude": lon},
        "radius_km": radius_km,
        "nearby_icebergs": nearby_icebergs[:10],
        "iceberg_count": len(nearby_icebergs),
        "nearest_iceberg": nearby_icebergs[0] if nearby_icebergs else None,
        "local_sea_ice": local_ice,
        "weather": weather_at_vessel,
        "assessed_at": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/vessels/{mmsi}/route")
async def calculate_vessel_route(
    mmsi: str,
    destination_lat: float = Query(...),
    destination_lon: float = Query(...),
    destination_name: str = Query(default="Destination"),
    route_type: str = Query(default="balanced"),
):
    """Calculate a route from a specific vessel's current position."""
    registry = get_registry()
    vessel = registry.get_vessel(mmsi)
    if not vessel:
        raise HTTPException(status_code=404, detail=f"Vessel '{mmsi}' not found")

    lat = vessel.get("latitude")
    lon = vessel.get("longitude")
    if lat is None or lon is None:
        raise HTTPException(status_code=422, detail="Vessel has no current position for routing")

    from app.services.route_service import generate_routes
    from app.schemas.routes import RouteGenerateRequest

    class _Req:
        origin_lat = lat
        origin_lon = lon
        origin_name = vessel.get("name", mmsi)
        destination_lat = destination_lat
        destination_lon = destination_lon
        destination_name = destination_name
        route_preference = route_type
        generate_all = True
        vessel_name = vessel.get("name", mmsi)
        departure_time = None

    result = generate_routes(_Req())
    result["vessel_mmsi"] = mmsi
    return result


# ── WebSocket: live vessel stream ──────────────────────────────────────────────

@router.websocket("/ws/vessels")
async def vessels_websocket(websocket: WebSocket):
    """
    WebSocket broadcasting ALL vessel position updates in real time.
    Frontend subscribes once and receives every position update.
    """
    await websocket.accept()
    logger.info(f"[ws/vessels] Client connected: {websocket.client}")

    # Send current vessel registry snapshot
    registry = get_registry()
    await websocket.send_text(json.dumps({
        "event": "VESSEL_REGISTRY_SNAPSHOT",
        "vessels": registry.get_all_positions(),
        "active_mmsi": registry.active_mmsi,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }, default=str))

    try:
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({
                    "event": "PING",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug(f"[ws/vessels] {e}")


@router.websocket("/ws/vessel/{mmsi}")
async def single_vessel_websocket(websocket: WebSocket, mmsi: str):
    """
    WebSocket for a specific vessel — receives only that vessel's updates.
    """
    await websocket.accept()
    registry = get_registry()

    # Send initial state
    vessel = registry.get_vessel(mmsi)
    await websocket.send_text(json.dumps({
        "event": "VESSEL_INITIAL",
        "mmsi": mmsi,
        "vessel": vessel,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }, default=str))

    try:
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
            except asyncio.TimeoutError:
                # Push latest position
                vessel = registry.get_vessel(mmsi)
                await websocket.send_text(json.dumps({
                    "event": "VESSEL_POSITION_UPDATED",
                    "mmsi": mmsi,
                    "vessel": vessel,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }, default=str))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug(f"[ws/vessel/{mmsi}] {e}")


# ── Legacy compatibility endpoints ────────────────────────────────────────────
# Keep old /api/vessels/position for existing frontend code

@router.get("/vessels/position")
async def get_active_vessel_position():
    """Active vessel position (legacy compatibility)."""
    resp = await get_active_vessel()
    vessel = resp.get("vessel")
    return {
        "position": vessel,
        "freshness": resp.get("freshness"),
        "status": resp.get("status"),
    }


@router.get("/vessels/track")
async def get_active_vessel_track(hours: float = 6.0):
    """Active vessel track (legacy compatibility)."""
    registry = get_registry()
    active_mmsi = registry.active_mmsi
    if not active_mmsi:
        # Try first vessel
        all_v = registry.get_all_positions()
        if all_v:
            active_mmsi = all_v[0]["mmsi"]

    if not active_mmsi:
        return {"track": [], "hours": hours, "is_real": False,
                "message": "No active vessel. Select a vessel first."}

    track = registry.get_track(active_mmsi, hours=hours)
    return {
        "track": track,
        "mmsi": active_mmsi,
        "hours": hours,
        "is_real": True,
        "data_mode": "live",
    }


# ── Utility ────────────────────────────────────────────────────────────────────

import math


def _bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate bearing from point 1 to point 2."""
    lat1r, lat2r = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon) * math.cos(lat2r)
    y = (math.cos(lat1r) * math.sin(lat2r)
         - math.sin(lat1r) * math.cos(lat2r) * math.cos(dlon))
    return (math.degrees(math.atan2(x, y)) + 360) % 360
