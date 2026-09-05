"""
POLAR-AI Vessel Source — AIS Adapter
=====================================
Provides a provider-agnostic AIS interface.

Supported providers (set via AIS_PROVIDER env var):
  - aisstream   → wss://stream.aisstream.io/v0/stream (free tier available)
  - barentswatch → https://live.ais.barentswatch.no/v1/
  - marinetraffic→ https://services.marinetraffic.com/api/
  - custom      → any REST endpoint

When no AIS provider is configured:
  - Returns DEMO mode vessel data
  - Never labels it LIVE
  - Never pretends position is real

Architecture:
  AISProvider (abstract)
       |
  ┌────┴────┬────────────┬───────────┐
  │         │            │           │
AISStream  BarentsWatch MarineTraffic Custom
"""
from __future__ import annotations
import asyncio
import json
import math
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, AsyncGenerator

import httpx
from loguru import logger

from app.core.freshness import FreshnessRegistry, DataStatus
from app.config import settings


class VesselPosition:
    """Normalized vessel position from any AIS provider."""
    def __init__(self, **kwargs):
        self.mmsi: str = kwargs.get("mmsi", "")
        self.imo: str = kwargs.get("imo", "")
        self.vessel_name: str = kwargs.get("vessel_name", "")
        self.latitude: float = kwargs.get("latitude", 0.0)
        self.longitude: float = kwargs.get("longitude", 0.0)
        self.speed_knots: float = kwargs.get("speed_knots", 0.0)
        self.course_deg: float = kwargs.get("course_deg", 0.0)
        self.heading_deg: float = kwargs.get("heading_deg", 0.0)
        self.navigation_status: str = kwargs.get("navigation_status", "underway")
        self.timestamp: datetime = kwargs.get("timestamp", datetime.now(timezone.utc))
        self.source: str = kwargs.get("source", "")
        self.is_real: bool = kwargs.get("is_real", False)

    def to_dict(self) -> Dict:
        age = (datetime.now(timezone.utc) - self.timestamp).total_seconds()
        return {
            "mmsi": self.mmsi,
            "imo": self.imo,
            "vessel_name": self.vessel_name,
            "latitude": round(self.latitude, 5),
            "longitude": round(self.longitude, 5),
            "speed_knots": round(self.speed_knots, 1),
            "course_deg": round(self.course_deg, 1),
            "heading_deg": round(self.heading_deg, 1),
            "navigation_status": self.navigation_status,
            "timestamp": self.timestamp.isoformat(),
            "age_seconds": round(age, 1),
            "source": self.source,
            "is_real": self.is_real,
            "data_mode": "live" if self.is_real else "demo",
        }


class AISStreamAdapter:
    """
    AISStream.io WebSocket adapter.
    Free tier: https://aisstream.io — requires free API key.
    Set: AIS_PROVIDER=aisstream, AIS_API_KEY=your_key, AIS_WS_URL=wss://stream.aisstream.io/v0/stream
    """
    def __init__(self):
        self._ws_url = settings.AIS_WS_URL or "wss://stream.aisstream.io/v0/stream"
        self._api_key = settings.AIS_API_KEY

    async def stream(self) -> AsyncGenerator[VesselPosition, None]:
        """Yields VesselPosition objects from the WebSocket stream."""
        try:
            import websockets
        except ImportError:
            logger.error("[ais] websockets package not installed — pip install websockets")
            return

        subscribe_msg = {
            "APIKey": self._api_key,
            "BoundingBoxes": [[[-90, -180], [-45, 180]]],  # Antarctic region
            "FilterMessageTypes": ["PositionReport"],
        }

        try:
            async with websockets.connect(self._ws_url) as ws:
                await ws.send(json.dumps(subscribe_msg))
                logger.info("[ais] AISStream WebSocket connected")
                FreshnessRegistry.update("ais", status=DataStatus.LIVE,
                                         last_updated=datetime.now(timezone.utc))
                async for raw_msg in ws:
                    try:
                        msg = json.loads(raw_msg)
                        pos = self._parse_message(msg)
                        if pos:
                            yield pos
                    except Exception as e:
                        logger.debug(f"[ais] Message parse error: {e}")
        except Exception as e:
            logger.error(f"[ais] WebSocket error: {e}")
            FreshnessRegistry.update("ais", last_error=str(e), status=DataStatus.OFFLINE)

    def _parse_message(self, msg: dict) -> Optional[VesselPosition]:
        try:
            meta = msg.get("MetaData", {})
            pos_report = msg.get("Message", {}).get("PositionReport", {})
            return VesselPosition(
                mmsi=str(meta.get("MMSI", "")),
                vessel_name=meta.get("ShipName", "").strip(),
                latitude=float(pos_report.get("Latitude", 0)),
                longitude=float(pos_report.get("Longitude", 0)),
                speed_knots=float(pos_report.get("Sog", 0)) / 10,
                course_deg=float(pos_report.get("Cog", 0)) / 10,
                heading_deg=float(pos_report.get("TrueHeading", 0)),
                navigation_status=str(pos_report.get("NavigationalStatus", "underway")),
                timestamp=datetime.now(timezone.utc),
                source="AISStream.io",
                is_real=True,
            )
        except Exception:
            return None


class BarentsWatchAdapter:
    """
    Barentswatch AIS REST API (Norwegian polar/Arctic vessel data).
    Free with registration: https://www.barentswatch.no/bwapi/
    Set: AIS_PROVIDER=barentswatch, AIS_API_KEY=..., AIS_API_URL=https://live.ais.barentswatch.no/v1/
    """
    async def get_vessels(self, mmsi: str = None) -> List[VesselPosition]:
        url = f"{settings.AIS_API_URL}latest/combined"
        headers = {"Authorization": f"Bearer {settings.AIS_API_KEY}"}
        params = {}
        if mmsi:
            params["mmsi"] = mmsi

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(url, headers=headers, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.error(f"[ais] BarentsWatch fetch failed: {e}")
            return []

        positions = []
        for vessel in data:
            try:
                positions.append(VesselPosition(
                    mmsi=str(vessel.get("mmsi", "")),
                    vessel_name=vessel.get("name", "").strip(),
                    latitude=float(vessel.get("latitude", 0)),
                    longitude=float(vessel.get("longitude", 0)),
                    speed_knots=float(vessel.get("speedOverGround", 0)),
                    course_deg=float(vessel.get("courseOverGround", 0)),
                    heading_deg=float(vessel.get("trueHeading", 0)),
                    timestamp=datetime.now(timezone.utc),
                    source="BarentsWatch",
                    is_real=True,
                ))
            except Exception:
                continue
        return positions


class GenericRestAdapter:
    """
    Generic REST adapter for any AIS provider.
    Set AIS_API_URL to the base REST endpoint.
    Expected response: array of vessel objects with lat/lon/mmsi/speed/course.
    """
    async def get_vessels(self) -> List[VesselPosition]:
        headers = {"Authorization": f"Bearer {settings.AIS_API_KEY}"}
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(settings.AIS_API_URL, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.error(f"[ais] Generic REST fetch failed: {e}")
            return []

        # Try common response formats
        vessels_raw = data if isinstance(data, list) else data.get("vessels", data.get("data", []))
        positions = []
        for v in vessels_raw:
            try:
                positions.append(VesselPosition(
                    mmsi=str(v.get("mmsi", v.get("MMSI", ""))),
                    vessel_name=str(v.get("name", v.get("shipname", v.get("vesselName", "")))),
                    latitude=float(v.get("lat", v.get("latitude", v.get("LAT", 0)))),
                    longitude=float(v.get("lon", v.get("longitude", v.get("LON", 0)))),
                    speed_knots=float(v.get("speed", v.get("sog", v.get("SOG", 0)))),
                    course_deg=float(v.get("course", v.get("cog", v.get("COG", 0)))),
                    heading_deg=float(v.get("heading", v.get("trueHeading", 0))),
                    timestamp=datetime.now(timezone.utc),
                    source=f"AIS/{settings.AIS_PROVIDER}",
                    is_real=True,
                ))
            except Exception:
                continue
        return positions


class VesselTrackingService:
    """
    Central vessel tracking service.
    Delegates to the configured AIS provider.
    Falls back to demo mode when no provider is configured.
    """

    def __init__(self):
        self._current_position: Optional[VesselPosition] = None
        self._track: List[Dict] = []  # recent positions
        self._max_track_points = 500
        self._provider = settings.AIS_PROVIDER.lower() if settings.AIS_PROVIDER else ""
        self._ws_task = None

    def is_live(self) -> bool:
        return settings.has_ais and self._current_position is not None

    def get_position(self) -> Dict:
        """Return current vessel position. NEVER labels demo data as LIVE."""
        if self._current_position and self._current_position.is_real:
            pos = self._current_position.to_dict()
            pos["data_mode"] = "live"
            pos["status_label"] = "LIVE"
            FreshnessRegistry.update("ais", status=DataStatus.LIVE,
                                     last_updated=self._current_position.timestamp)
            return pos

        # Demo mode
        return self._demo_position()

    def _demo_position(self) -> Dict:
        """Deterministic demo vessel position — clearly labeled DEMO."""
        return {
            "mmsi": "DEMO",
            "imo": "DEMO",
            "vessel_name": "RV Polar Explorer (DEMO)",
            "latitude": -66.0,
            "longitude": -60.0,
            "speed_knots": 11.5,
            "course_deg": 145.0,
            "heading_deg": 145.0,
            "navigation_status": "underway",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "age_seconds": 0,
            "source": "demo",
            "is_real": False,
            "data_mode": "demo",
            "status_label": "DEMO",
        }

    def get_track(self, hours: int = 6) -> List[Dict]:
        """Return recent vessel track."""
        if not self._track:
            return self._demo_track(hours)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        return [p for p in self._track if
                datetime.fromisoformat(p.get("timestamp", "2000-01-01T00:00:00+00:00")) > cutoff]

    def _demo_track(self, hours: int = 6) -> List[Dict]:
        """Generate a synthetic vessel track."""
        track = []
        now = datetime.now(timezone.utc)
        lat, lon = -66.0, -60.0
        for i in range(hours * 2):
            t = now - timedelta(minutes=30 * i)
            lat += 0.01
            lon -= 0.015
            track.append({
                "latitude": round(lat, 4), "longitude": round(lon, 4),
                "speed_knots": 11.5, "course_deg": 145.0,
                "timestamp": t.isoformat(),
                "is_real": False, "data_mode": "demo",
            })
        return list(reversed(track))

    def update_position(self, pos: VesselPosition):
        """Update current position (called by WebSocket ingestion)."""
        self._current_position = pos
        track_point = pos.to_dict()
        self._track.append(track_point)
        if len(self._track) > self._max_track_points:
            self._track = self._track[-self._max_track_points:]
        FreshnessRegistry.update("ais", last_updated=pos.timestamp, status=DataStatus.LIVE)

    async def poll_once(self):
        """Single poll for REST-based AIS providers."""
        if not settings.has_ais:
            return

        provider = settings.AIS_PROVIDER.lower()
        positions = []

        try:
            if provider == "barentswatch":
                adapter = BarentsWatchAdapter()
                mmsi = settings.AIS_VESSEL_MMSI or None
                positions = await adapter.get_vessels(mmsi=mmsi)
            elif settings.AIS_API_URL:
                adapter = GenericRestAdapter()
                positions = await adapter.get_vessels()

            if positions:
                # Filter to specified MMSI if set
                if settings.AIS_VESSEL_MMSI:
                    positions = [p for p in positions if p.mmsi == settings.AIS_VESSEL_MMSI]
                if positions:
                    self.update_position(positions[0])
                    logger.info(f"[ais] Updated vessel: {positions[0].vessel_name} @ "
                                f"{positions[0].latitude:.4f},{positions[0].longitude:.4f}")
        except Exception as e:
            logger.error(f"[ais] Poll failed: {e}")
            FreshnessRegistry.update("ais", last_error=str(e), status=DataStatus.OFFLINE)


# Singleton
_vessel_service: Optional[VesselTrackingService] = None


def get_vessel_service() -> VesselTrackingService:
    global _vessel_service
    if _vessel_service is None:
        _vessel_service = VesselTrackingService()
    return _vessel_service
