"""
POLAR-AI Vessel Source — AIS Adapter
=====================================
LIVE mode rule: If no AIS provider is configured, return OFFLINE.
NEVER show hardcoded -66,-60 as a "live" position.

Supported providers:
  aisstream   → wss://stream.aisstream.io/v0/stream  (free tier, WebSocket)
  barentswatch → https://live.ais.barentswatch.no/v1/ (REST, free with account)
  custom       → any REST endpoint returning vessel JSON

DEMO mode (DATA_MODE=demo only):
  Returns clearly-labelled DEMO position with is_real=False.
  The map shows a static vessel icon with "DEMO" label.
  Never shown in LIVE mode.
"""
from __future__ import annotations
import asyncio
import json
import math
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, AsyncGenerator

import httpx
from loguru import logger

from app.core.freshness import FreshnessRegistry, DataStatus
from app.config import settings


# ── Normalised vessel position ─────────────────────────────────────────────────

class VesselPosition:
    def __init__(self, **kwargs):
        self.mmsi: str             = kwargs.get("mmsi", "")
        self.imo: str              = kwargs.get("imo", "")
        self.vessel_name: str      = kwargs.get("vessel_name", "")
        self.latitude: float       = kwargs.get("latitude", 0.0)
        self.longitude: float      = kwargs.get("longitude", 0.0)
        self.speed_knots: float    = kwargs.get("speed_knots", 0.0)
        self.course_deg: float     = kwargs.get("course_deg", 0.0)
        self.heading_deg: float    = kwargs.get("heading_deg", 0.0)
        self.navigation_status: str = kwargs.get("navigation_status", "underway")
        self.timestamp: datetime   = kwargs.get("timestamp", datetime.now(timezone.utc))
        self.source: str           = kwargs.get("source", "")
        self.is_real: bool         = kwargs.get("is_real", False)

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
            "status_label": "LIVE" if self.is_real else "DEMO",
        }


# ── OFFLINE response (LIVE mode with no AIS) ──────────────────────────────────

def _ais_offline_response() -> Dict:
    """
    Returned in LIVE mode when AIS is not configured or provider failed.
    NEVER shows fake coordinates.
    """
    f = FreshnessRegistry.get("ais")
    last_ok = f.last_updated.isoformat() if (f and f.last_updated) else None
    last_err = f.last_error if f else None
    return {
        "status": "OFFLINE",
        "source_id": "ais",
        "vessel_name": None,
        "latitude": None,
        "longitude": None,
        "speed_knots": None,
        "heading_deg": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "age_seconds": None,
        "is_real": False,
        "data_mode": "offline",
        "status_label": "AIS NOT CONNECTED",
        "message": (
            "Vessel tracking is not connected. "
            "Set AIS_PROVIDER and AIS_API_KEY to enable real AIS data. "
            "Supported providers: aisstream, barentswatch, custom REST."
        ),
        "last_successful_update": last_ok,
        "last_error": last_err,
        "setup_instructions": {
            "aisstream": "Register at https://aisstream.io/ (free) → set AIS_PROVIDER=aisstream, AIS_API_KEY=<key>, AIS_WS_URL=wss://stream.aisstream.io/v0/stream",
            "barentswatch": "Register at https://www.barentswatch.no/bwapi/ → set AIS_PROVIDER=barentswatch, AIS_API_KEY=<token>, AIS_API_URL=https://live.ais.barentswatch.no/v1/",
        },
    }


# ── AIS Provider Adapters ──────────────────────────────────────────────────────

class AISStreamAdapter:
    """AISStream.io WebSocket — free tier, covers global waters including Antarctica."""

    def __init__(self):
        self._ws_url = settings.AIS_WS_URL or "wss://stream.aisstream.io/v0/stream"
        self._api_key = settings.AIS_API_KEY

    async def stream(self) -> AsyncGenerator[VesselPosition, None]:
        try:
            import websockets
        except ImportError:
            logger.error("[ais] Install websockets: pip install websockets")
            return

        subscribe_msg = {
            "APIKey": self._api_key,
            "BoundingBoxes": [[[-90, -180], [-45, 180]]],
            "FilterMessageTypes": ["PositionReport"],
        }

        try:
            async with websockets.connect(self._ws_url, ping_interval=30) as ws:
                await ws.send(json.dumps(subscribe_msg))
                logger.info("[ais] AISStream WebSocket connected — monitoring Antarctic region")
                FreshnessRegistry.update("ais", status=DataStatus.LIVE,
                                         last_updated=datetime.now(timezone.utc))
                async for raw in ws:
                    try:
                        pos = self._parse(json.loads(raw))
                        if pos:
                            yield pos
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"[ais] AISStream WS error: {e}")
            FreshnessRegistry.update("ais", last_error=str(e), status=DataStatus.OFFLINE)

    def _parse(self, msg: dict) -> Optional[VesselPosition]:
        try:
            meta = msg.get("MetaData", {})
            pos = msg.get("Message", {}).get("PositionReport", {})
            lat = float(pos.get("Latitude", 0))
            lon = float(pos.get("Longitude", 0))
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                return None
            return VesselPosition(
                mmsi=str(meta.get("MMSI", "")),
                vessel_name=meta.get("ShipName", "").strip(),
                latitude=lat, longitude=lon,
                speed_knots=float(pos.get("Sog", 0)) / 10,
                course_deg=float(pos.get("Cog", 0)) / 10,
                heading_deg=float(pos.get("TrueHeading", 0)),
                navigation_status=str(pos.get("NavigationalStatus", "underway")),
                timestamp=datetime.now(timezone.utc),
                source="AISStream.io", is_real=True,
            )
        except Exception:
            return None


class BarentsWatchAdapter:
    """BarentsWatch REST AIS — Norwegian polar/Arctic vessel tracking."""

    async def get_vessels(self, mmsi: str = None) -> List[VesselPosition]:
        url = f"{settings.AIS_API_URL.rstrip('/')}/latest/combined"
        headers = {"Authorization": f"Bearer {settings.AIS_API_KEY}"}
        params = {"mmsi": mmsi} if mmsi else {}
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(url, headers=headers, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.error(f"[ais] BarentsWatch fetch failed: {e}")
            return []

        return [
            VesselPosition(
                mmsi=str(v.get("mmsi", "")),
                vessel_name=str(v.get("name", "")).strip(),
                latitude=float(v.get("latitude", 0)),
                longitude=float(v.get("longitude", 0)),
                speed_knots=float(v.get("speedOverGround", 0)),
                course_deg=float(v.get("courseOverGround", 0)),
                heading_deg=float(v.get("trueHeading", 0)),
                timestamp=datetime.now(timezone.utc),
                source="BarentsWatch", is_real=True,
            )
            for v in data if v.get("latitude") and v.get("longitude")
        ]


class GenericRestAdapter:
    """Generic REST adapter for any AIS provider."""

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

        vessels_raw = data if isinstance(data, list) else data.get(
            "vessels", data.get("data", data.get("results", [])))

        positions = []
        for v in vessels_raw:
            try:
                lat = float(v.get("lat", v.get("latitude", v.get("LAT", 0))))
                lon = float(v.get("lon", v.get("longitude", v.get("LON", 0))))
                if not (-90 <= lat <= 90 and -180 <= lon <= 180) or (lat == 0 and lon == 0):
                    continue
                positions.append(VesselPosition(
                    mmsi=str(v.get("mmsi", v.get("MMSI", ""))),
                    vessel_name=str(v.get("name", v.get("shipname", v.get("vesselName", "")))),
                    latitude=lat, longitude=lon,
                    speed_knots=float(v.get("speed", v.get("sog", v.get("SOG", 0)))),
                    course_deg=float(v.get("course", v.get("cog", v.get("COG", 0)))),
                    heading_deg=float(v.get("heading", v.get("trueHeading", 0))),
                    timestamp=datetime.now(timezone.utc),
                    source=f"AIS/{settings.AIS_PROVIDER}", is_real=True,
                ))
            except Exception:
                continue
        return positions


# ── Central Vessel Tracking Service ───────────────────────────────────────────

class VesselTrackingService:
    """
    Central service for vessel position. Delegates to AIS provider.

    LIVE mode (DATA_MODE=live or auto with AIS configured):
      - Returns real AIS position
      - If no position yet: returns OFFLINE response, NOT fake coords

    DEMO mode (DATA_MODE=demo):
      - Returns clearly-labelled DEMO position
      - Labelled "DEMO", is_real=False, status_label="DEMO"
    """

    def __init__(self):
        self._position: Optional[VesselPosition] = None
        self._track: List[Dict] = []
        self._max_track = 500
        self._provider = (settings.AIS_PROVIDER or "").lower()

    def is_live(self) -> bool:
        return settings.has_ais and self._position is not None and self._position.is_real

    def get_position(self) -> Dict:
        """
        Returns vessel position.
        LIVE mode: real position or OFFLINE (never fake coords).
        DEMO mode: clearly labelled synthetic position.
        """
        from app.config import settings as _s
        from app.core.live_gate import allow_demo_fallback

        # Real position available
        if self._position and self._position.is_real:
            pos = self._position.to_dict()
            FreshnessRegistry.update("ais", status=DataStatus.LIVE,
                                     last_updated=self._position.timestamp)
            return pos

        # LIVE mode, no real position → OFFLINE (do NOT show fake coords)
        if not allow_demo_fallback():
            return _ais_offline_response()

        # Demo mode — only if explicitly allowed
        if _s.DATA_MODE.lower() == "demo" or _s.effective_data_mode == "demo":
            return self._demo_position()

        # Auto mode without AIS configured → OFFLINE
        if not settings.has_ais:
            return _ais_offline_response()

        # AIS configured but not yet received a position → OFFLINE (not fake)
        return _ais_offline_response()

    def _demo_position(self) -> Dict:
        """
        Demo vessel position — ONLY used in explicit DEMO mode.
        Clearly labelled. Never shown as LIVE.
        """
        return {
            "mmsi": "DEMO",
            "imo": "DEMO",
            "vessel_name": "RV Polar Explorer [DEMO MODE]",
            "latitude": -66.0,
            "longitude": -60.0,
            "speed_knots": 11.5,
            "course_deg": 145.0,
            "heading_deg": 145.0,
            "navigation_status": "underway",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "age_seconds": 0.0,
            "source": "demo",
            "is_real": False,
            "data_mode": "demo",
            "status_label": "DEMO",
            "message": "This is a simulated vessel position. Set AIS credentials for real tracking.",
        }

    def get_track(self, hours: int = 6) -> Dict:
        """Return vessel track. OFFLINE in LIVE mode if no real data."""
        from app.core.live_gate import allow_demo_fallback

        if not allow_demo_fallback() and not self._track:
            return {
                "status": "OFFLINE",
                "track": [],
                "hours": hours,
                "is_real": False,
                "message": "No vessel track available. AIS not connected.",
            }

        if self._track:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
            real_track = [p for p in self._track if
                          _parse_ts(p.get("timestamp")) > cutoff]
            if real_track:
                return {
                    "track": real_track,
                    "hours": hours,
                    "is_real": True,
                    "point_count": len(real_track),
                }

        if not allow_demo_fallback():
            return {
                "status": "INSUFFICIENT_DATA",
                "track": [],
                "hours": hours,
                "is_real": False,
                "message": f"Insufficient track history. Need real AIS data for {hours}h track.",
            }

        return {
            "track": self._demo_track(hours),
            "hours": hours,
            "is_real": False,
            "is_demo": True,
            "message": "DEMO track — not real vessel positions.",
        }

    def _demo_track(self, hours: int = 6) -> List[Dict]:
        """Synthetic track used only in DEMO mode."""
        track = []
        now = datetime.now(timezone.utc)
        lat, lon = -66.0, -60.0
        for i in range(hours * 2):
            t = now - timedelta(minutes=30 * i)
            lat += 0.01; lon -= 0.015
            track.append({
                "latitude": round(lat, 4), "longitude": round(lon, 4),
                "speed_knots": 11.5, "course_deg": 145.0,
                "timestamp": t.isoformat(),
                "is_real": False, "data_mode": "demo",
            })
        return list(reversed(track))

    def update_position(self, pos: VesselPosition):
        self._position = pos
        self._track.append(pos.to_dict())
        if len(self._track) > self._max_track:
            self._track = self._track[-self._max_track:]
        FreshnessRegistry.update("ais", last_updated=pos.timestamp, status=DataStatus.LIVE)

    async def poll_once(self):
        """Single REST poll. Called by hourly scheduler."""
        if not settings.has_ais:
            return

        provider = self._provider
        positions: List[VesselPosition] = []

        try:
            if provider == "barentswatch":
                adapter = BarentsWatchAdapter()
                positions = await adapter.get_vessels(
                    mmsi=settings.AIS_VESSEL_MMSI or None)
            elif provider in ("aisstream",):
                # WebSocket provider — skip REST poll
                return
            elif settings.AIS_API_URL:
                adapter = GenericRestAdapter()
                positions = await adapter.get_vessels()

            if settings.AIS_VESSEL_MMSI and positions:
                positions = [p for p in positions
                             if p.mmsi == settings.AIS_VESSEL_MMSI]

            if positions:
                self.update_position(positions[0])
                p = positions[0]
                logger.info(f"[ais] Updated: {p.vessel_name} @ {p.latitude:.4f},{p.longitude:.4f}")
            else:
                logger.warning("[ais] Poll returned no vessel positions")
                FreshnessRegistry.update("ais", status=DataStatus.OFFLINE,
                                         last_error="No vessel positions in response")
        except Exception as e:
            logger.error(f"[ais] Poll failed: {e}")
            FreshnessRegistry.update("ais", last_error=str(e), status=DataStatus.OFFLINE)


def _parse_ts(ts_str: str) -> datetime:
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


# ── Singleton ─────────────────────────────────────────────────────────────────
_vessel_service: Optional[VesselTrackingService] = None


def get_vessel_service() -> VesselTrackingService:
    global _vessel_service
    if _vessel_service is None:
        _vessel_service = VesselTrackingService()
    return _vessel_service
