"""
POLAR-AI AIS Manager
====================
Central manager for ALL vessels visible from the AIS stream.

Key responsibilities:
  1. Store every vessel seen from the stream in-memory (vessel registry)
  2. Maintain position history per vessel (last 500 points)
  3. Provide search by MMSI, name, ship type, status
  4. Support ACTIVE VESSEL selection (persisted per API session via /api/vessels/active)
  5. Broadcast WebSocket events on every new position
  6. Periodically expire stale vessels (not seen > 24h)

The manager is a singleton — one instance for the entire backend process.
"""
from __future__ import annotations
import asyncio
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set, Any, Callable
from loguru import logger

from app.services.ais.ais_normalizer import NormalizedVessel, from_aisstream
from app.config import settings


class VesselRegistry:
    """
    In-memory store of all vessels currently visible from AIS.
    Thread-safe via asyncio (single-threaded event loop).
    """

    def __init__(self):
        # mmsi → latest NormalizedVessel
        self._vessels: Dict[str, NormalizedVessel] = {}
        # mmsi → list of recent position dicts (max 500 per vessel)
        self._tracks: Dict[str, List[dict]] = {}
        # active vessel MMSI (globally selected by user)
        self._active_mmsi: Optional[str] = None
        # broadcast callback — set by main.py
        self._broadcast_fn: Optional[Callable] = None
        # WS connection count
        self._ws_clients: int = 0
        # max track points per vessel
        self._max_track = 500
        # MMSI filter (from AIS_VESSEL_MMSI env var, comma-separated)
        mmsi_filter = (settings.AIS_VESSEL_MMSI or "").strip()
        self._mmsi_filter: Set[str] = {
            m.strip() for m in mmsi_filter.split(",") if m.strip()
        } if mmsi_filter else set()

    # ── Ingestion ──────────────────────────────────────────────────────────────

    def update_vessel(self, vessel: NormalizedVessel) -> bool:
        """
        Store/update a vessel. Returns True if the vessel has a valid position.
        Applies MMSI filter if configured.
        """
        if not vessel.mmsi:
            return False

        # Apply MMSI filter if set
        if self._mmsi_filter and vessel.mmsi not in self._mmsi_filter:
            return False

        # Only store if valid Antarctic-region position (lat < -45 or no filter set)
        # Accept all Antarctic + sub-Antarctic vessels (-90 to -40)
        if vessel.is_valid_position():
            if vessel.latitude is not None and vessel.latitude > -40:
                return False  # outside Antarctic region

        # Merge with existing record (keep known fields if new message lacks them)
        existing = self._vessels.get(vessel.mmsi)
        if existing:
            if not vessel.name and existing.name:
                vessel.name = existing.name
            if not vessel.imo and existing.imo:
                vessel.imo = existing.imo
            if not vessel.call_sign and existing.call_sign:
                vessel.call_sign = existing.call_sign
            if not vessel.ship_type_name and existing.ship_type_name:
                vessel.ship_type_name = existing.ship_type_name
                vessel.ship_type = existing.ship_type
            if not vessel.destination and existing.destination:
                vessel.destination = existing.destination

        self._vessels[vessel.mmsi] = vessel

        # Add to track if valid position
        if vessel.is_valid_position():
            track = self._tracks.setdefault(vessel.mmsi, [])
            track.append({
                "latitude": vessel.latitude,
                "longitude": vessel.longitude,
                "speed": vessel.speed,
                "course": vessel.course,
                "heading": vessel.heading,
                "timestamp": vessel.timestamp.isoformat(),
            })
            if len(track) > self._max_track:
                self._tracks[vessel.mmsi] = track[-self._max_track:]

        return True

    # ── Query ──────────────────────────────────────────────────────────────────

    def search(self, query: str = "", limit: int = 50) -> List[dict]:
        """Search vessels by name, MMSI, or IMO."""
        q = query.lower().strip()
        results = []
        for v in self._vessels.values():
            if not q:
                results.append(v.to_dict())
            elif (q in v.mmsi.lower()
                  or q in v.name.lower()
                  or (v.imo and q in v.imo.lower())
                  or (v.call_sign and q in v.call_sign.lower())):
                results.append(v.to_dict())

        # Sort: active vessel first, then by most recently updated
        active = self._active_mmsi
        results.sort(key=lambda v: (
            0 if v["mmsi"] == active else 1,
            -(datetime.fromisoformat(v["timestamp"])
              .replace(tzinfo=timezone.utc).timestamp()
              if v.get("timestamp") else 0)
        ))
        return results[:limit]

    def get_vessel(self, mmsi: str) -> Optional[dict]:
        v = self._vessels.get(mmsi)
        return v.to_dict() if v else None

    def get_track(self, mmsi: str, hours: float = 6) -> List[dict]:
        track = self._tracks.get(mmsi, [])
        if not track:
            return []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        return [
            p for p in track
            if datetime.fromisoformat(p["timestamp"]).replace(tzinfo=timezone.utc) > cutoff
        ]

    def get_all_positions(self) -> List[dict]:
        """All known vessels with valid positions (for map display)."""
        return [
            v.to_dict() for v in self._vessels.values()
            if v.is_valid_position()
        ]

    def vessel_count(self) -> int:
        return len(self._vessels)

    def get_active_vessel(self) -> Optional[dict]:
        if self._active_mmsi:
            return self.get_vessel(self._active_mmsi)
        # If no active vessel selected but we have vessels, return the most recent
        if self._vessels:
            latest = max(self._vessels.values(), key=lambda v: v.timestamp)
            return latest.to_dict()
        return None

    def set_active_vessel(self, mmsi: str) -> bool:
        if mmsi in self._vessels:
            self._active_mmsi = mmsi
            logger.info(f"[ais_manager] Active vessel set to {mmsi} "
                        f"({self._vessels[mmsi].name})")
            return True
        return False

    @property
    def active_mmsi(self) -> Optional[str]:
        return self._active_mmsi

    # ── Stale vessel expiry ────────────────────────────────────────────────────

    def expire_stale(self, max_age_hours: float = 24):
        """Remove vessels not seen for max_age_hours."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        stale = [
            mmsi for mmsi, v in self._vessels.items()
            if v.timestamp < cutoff
        ]
        for mmsi in stale:
            del self._vessels[mmsi]
            self._tracks.pop(mmsi, None)
        if stale:
            logger.info(f"[ais_manager] Expired {len(stale)} stale vessels")

    # ── Broadcast hook ─────────────────────────────────────────────────────────

    def set_broadcast_fn(self, fn: Callable):
        self._broadcast_fn = fn

    async def broadcast_position(self, vessel: NormalizedVessel):
        if not self._broadcast_fn:
            return
        payload = {
            "event": "VESSEL_POSITION_UPDATED",
            "mmsi": vessel.mmsi,
            "vessel": vessel.to_dict(),
            "is_active": vessel.mmsi == self._active_mmsi,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        try:
            await self._broadcast_fn(payload)
        except Exception as e:
            logger.debug(f"[ais_manager] Broadcast failed: {e}")

    # ── DB persistence (non-blocking) ──────────────────────────────────────────

    async def persist_position(self, vessel: NormalizedVessel):
        """Write vessel position to DB (non-fatal if DB unavailable)."""
        if not vessel.is_valid_position():
            return
        try:
            from app.database import SessionLocal
            from sqlalchemy import text
            db = SessionLocal()
            try:
                db.execute(text("""
                    INSERT INTO vessel_positions
                      (id, vessel_name, mmsi, latitude, longitude,
                       speed_knots, course_deg, heading_deg,
                       navigation_status, observed_at, source,
                       is_real, data_mode)
                    VALUES
                      (uuid_generate_v4(), :name, :mmsi, :lat, :lon,
                       :speed, :course, :heading,
                       :nav_status, :observed, :source,
                       true, 'live')
                """), {
                    "name": vessel.name or vessel.mmsi,
                    "mmsi": vessel.mmsi,
                    "lat": vessel.latitude,
                    "lon": vessel.longitude,
                    "speed": vessel.speed,
                    "course": vessel.course,
                    "heading": vessel.heading,
                    "nav_status": vessel.navigation_status,
                    "observed": vessel.timestamp,
                    "source": vessel.source,
                })
                db.commit()
            finally:
                db.close()
        except Exception:
            pass  # non-fatal


# ── Singleton ─────────────────────────────────────────────────────────────────
_registry: Optional[VesselRegistry] = None


def get_registry() -> VesselRegistry:
    global _registry
    if _registry is None:
        _registry = VesselRegistry()
    return _registry


# ── AISStream listener ─────────────────────────────────────────────────────────

_aisstream_task: Optional[asyncio.Task] = None


def ensure_aisstream_running():
    """Start the AISStream WebSocket listener if not already running."""
    global _aisstream_task
    if _aisstream_task and not _aisstream_task.done():
        return

    async def _run():
        registry = get_registry()
        try:
            import websockets
        except ImportError:
            logger.error("[ais] Install websockets: pip install websockets")
            return

        ws_url = settings.AIS_WS_URL or "wss://stream.aisstream.io/v0/stream"
        api_key = settings.AIS_API_KEY

        subscribe_msg = {
            "APIKey": api_key,
            # All Antarctic and sub-Antarctic vessels
            "BoundingBoxes": [[[-90, -180], [-40, 180]]],
            "FilterMessageTypes": [
                "PositionReport",
                "StandardClassBPositionReport",
                "ShipStaticData",
            ],
        }

        retry_delay = 5
        logger.info("[ais] Starting AISStream listener — Antarctic bounding box")

        while True:
            try:
                async with websockets.connect(
                    ws_url,
                    ping_interval=30,
                    ping_timeout=10,
                    close_timeout=5,
                ) as ws:
                    await ws.send(json.dumps(subscribe_msg))
                    logger.info("[ais] AISStream connected")

                    from app.core.freshness import FreshnessRegistry, DataStatus
                    FreshnessRegistry.update("ais",
                        status=DataStatus.LIVE,
                        last_updated=datetime.now(timezone.utc))

                    retry_delay = 5  # reset on success

                    async for raw in ws:
                        try:
                            msg = json.loads(raw)
                            vessel = from_aisstream(msg)
                            if vessel and registry.update_vessel(vessel):
                                # Broadcast position update
                                await registry.broadcast_position(vessel)
                                # Persist to DB (fire and forget)
                                asyncio.create_task(
                                    registry.persist_position(vessel))

                                FreshnessRegistry.update("ais",
                                    status=DataStatus.LIVE,
                                    last_updated=vessel.timestamp,
                                    record_count=registry.vessel_count())
                        except json.JSONDecodeError:
                            pass
                        except Exception as e:
                            logger.debug(f"[ais] Message parse: {e}")

            except Exception as e:
                logger.warning(f"[ais] Stream error ({e}), retry in {retry_delay}s")
                from app.core.freshness import FreshnessRegistry, DataStatus
                FreshnessRegistry.update("ais",
                    last_error=str(e),
                    status=DataStatus.OFFLINE)
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 300)

    _aisstream_task = asyncio.create_task(_run())
