"""
POLAR-AI Hourly Update Orchestrator
=====================================
Runs every UPDATE_INTERVAL_MINUTES (default 60) and refreshes all
external data sources. Stores results in PostgreSQL.

Architecture:
  Scheduler → run_hourly_update()
     ├── update_satellite()
     ├── update_sea_ice()
     ├── update_icebergs()
     ├── update_weather()
     ├── update_ocean()
     ├── update_vessels()
     ├── recalculate_risk()
     ├── check_routes()
     └── publish_updates()  ← broadcasts WebSocket events

Every task records:
  started_at, finished_at, status, records_received, records_saved,
  source, error, observation_time

LIVE mode rule:
  If a source fails → mark OFFLINE, do NOT fall back to demo data.
  Retain the last real observation with its exact timestamp.
"""
from __future__ import annotations
import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from loguru import logger

from app.config import settings
from app.core.freshness import FreshnessRegistry, DataStatus


# ── In-memory run state (DB writes are additive) ──────────────────────────────
_current_run: Optional[Dict] = None
_run_history: List[Dict] = []           # last 24 runs
_run_counter: int = 0
_next_run_at: Optional[datetime] = None
_ws_broadcast_fn = None                  # set by WebSocket module at startup


def set_broadcast_fn(fn):
    """Register the WebSocket broadcast function."""
    global _ws_broadcast_fn
    _ws_broadcast_fn = fn


def get_current_run() -> Optional[Dict]:
    return _current_run


def get_run_history(limit: int = 24) -> List[Dict]:
    return _run_history[-limit:]


def get_next_run_at() -> Optional[datetime]:
    return _next_run_at


# ── Task result builder ────────────────────────────────────────────────────────

def _task(source_id: str) -> Dict:
    return {
        "source_id": source_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
        "status": "running",
        "records_received": 0,
        "records_saved": 0,
        "error": None,
        "observation_time": None,
        "note": None,
    }


def _finish_task(t: Dict, status: str, records_received: int = 0,
                 records_saved: int = 0, observation_time=None,
                 error: str = None, note: str = None) -> Dict:
    t.update({
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "records_received": records_received,
        "records_saved": records_saved,
        "error": error,
        "observation_time": observation_time.isoformat() if observation_time else None,
        "note": note,
    })
    return t


# ── Individual source updaters ────────────────────────────────────────────────

async def update_satellite(run_id: str) -> Dict:
    t = _task("satellite")
    try:
        from app.sources.satellite_source import get_satellite_source
        from app.core.freshness import FreshnessRegistry, DataStatus

        src = get_satellite_source()
        if not src.is_configured():
            return _finish_task(t, "skipped",
                note="COPERNICUS_CLIENT_ID / COPERNICUS_CLIENT_SECRET not configured")

        products = await src.fetch()
        if products:
            latest = src.get_latest_product()
            obs_time = None
            if latest and latest.get("acquisition_time"):
                try:
                    obs_time = datetime.fromisoformat(
                        latest["acquisition_time"].replace("Z", "+00:00"))
                except Exception:
                    pass
            FreshnessRegistry.update("satellite", status=DataStatus.LATEST_AVAILABLE,
                                     last_updated=datetime.now(timezone.utc),
                                     record_count=len(products))
            return _finish_task(t, "success",
                records_received=len(products), records_saved=len(products),
                observation_time=obs_time,
                note=f"Latest: {latest.get('product_id','?') if latest else '?'}")
        else:
            return _finish_task(t, "no_new_data",
                note="No new Sentinel-1 products found in search window")
    except Exception as e:
        FreshnessRegistry.update("satellite", last_error=str(e), status=DataStatus.OFFLINE)
        return _finish_task(t, "failed", error=str(e))


async def update_sea_ice(run_id: str) -> Dict:
    t = _task("sea_ice")
    try:
        from app.sources.sea_ice_source import get_sea_ice_source
        from app.core.freshness import FreshnessRegistry, DataStatus

        src = get_sea_ice_source()
        result = await src.fetch()

        daily = src.get_history(days=7)
        latest = daily[-1] if daily else src.get_latest_extent()

        obs_time = None
        if latest and latest.get("date"):
            try:
                obs_time = datetime.strptime(latest["date"], "%Y-%m-%d").replace(
                    tzinfo=timezone.utc)
            except Exception:
                pass

        n = len(src.get_history(days=365))

        # Persist to DB if available
        saved = await _persist_sea_ice(latest, run_id)

        FreshnessRegistry.update("sea_ice", status=DataStatus.LATEST_AVAILABLE,
                                 last_updated=datetime.now(timezone.utc),
                                 record_count=n)
        return _finish_task(t, "success",
            records_received=n, records_saved=saved,
            observation_time=obs_time,
            note=f"Coverage: {latest.get('coverage_pct','?')}% "
                 f"Extent: {latest.get('extent_km2','?')/1e6:.2f}M km²" if latest else "")
    except Exception as e:
        FreshnessRegistry.update("sea_ice", last_error=str(e), status=DataStatus.OFFLINE)
        return _finish_task(t, "failed", error=str(e))


async def _persist_sea_ice(latest: Optional[Dict], run_id: str) -> int:
    """Write latest sea-ice observation to DB if possible."""
    if not latest:
        return 0
    try:
        from app.database import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        try:
            db.execute(text("""
                INSERT INTO live_sea_ice_observations
                  (id, observation_date, extent_km2, area_km2, coverage_pct,
                   source, retrieved_at, run_id)
                VALUES
                  (uuid_generate_v4(), :obs_date, :extent, :area, :coverage,
                   :source, :retrieved, :run_id)
                ON CONFLICT (observation_date) DO UPDATE SET
                  extent_km2 = EXCLUDED.extent_km2,
                  coverage_pct = EXCLUDED.coverage_pct,
                  retrieved_at = EXCLUDED.retrieved_at
            """), {
                "obs_date": latest.get("date"),
                "extent": latest.get("extent_km2"),
                "area": latest.get("area_km2"),
                "coverage": latest.get("coverage_pct"),
                "source": latest.get("source", "NSIDC G02135 v3"),
                "retrieved": datetime.now(timezone.utc),
                "run_id": run_id,
            })
            db.commit()
            return 1
        finally:
            db.close()
    except Exception as e:
        logger.debug(f"[sea_ice] DB persist failed (non-fatal): {e}")
        return 0


async def update_icebergs(run_id: str) -> Dict:
    t = _task("icebergs")
    try:
        from app.sources.iceberg_source import get_iceberg_source
        from app.core.freshness import FreshnessRegistry, DataStatus

        src = get_iceberg_source()
        icebergs = await src.fetch()

        obs_time = datetime.now(timezone.utc)  # NIC doesn't always have precise timestamps

        # Persist to DB
        saved = await _persist_icebergs(icebergs, run_id)

        FreshnessRegistry.update("icebergs", status=DataStatus.LATEST_AVAILABLE,
                                 last_updated=datetime.now(timezone.utc),
                                 record_count=len(icebergs))
        return _finish_task(t, "success" if icebergs else "no_new_data",
            records_received=len(icebergs), records_saved=saved,
            observation_time=obs_time,
            note=f"{len(icebergs)} icebergs from US National Ice Center")
    except Exception as e:
        FreshnessRegistry.update("icebergs", last_error=str(e), status=DataStatus.OFFLINE)
        return _finish_task(t, "failed", error=str(e))


async def _persist_icebergs(icebergs: List[Dict], run_id: str) -> int:
    if not icebergs:
        return 0
    saved = 0
    try:
        from app.database import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        try:
            for ib in icebergs:
                db.execute(text("""
                    INSERT INTO live_iceberg_observations
                      (id, retrieved_at, iceberg_name, latitude, longitude,
                       length_km, width_km, area_km2, observed_at, source, run_id)
                    VALUES
                      (uuid_generate_v4(), :retrieved, :name, :lat, :lon,
                       :length, :width, :area, :observed, :source, :run_id)
                """), {
                    "retrieved": datetime.now(timezone.utc),
                    "name": ib.get("iceberg_name", "?"),
                    "lat": ib.get("latitude"), "lon": ib.get("longitude"),
                    "length": ib.get("length_km"), "width": ib.get("width_km"),
                    "area": ib.get("area_km2"),
                    "observed": ib.get("last_observed_at"),
                    "source": ib.get("source", "US National Ice Center"),
                    "run_id": run_id,
                })
                saved += 1
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.debug(f"[icebergs] DB persist failed (non-fatal): {e}")
    return saved


async def update_weather(run_id: str) -> Dict:
    t = _task("weather")
    try:
        from app.sources.weather_source import get_weather_source
        from app.core.freshness import FreshnessRegistry, DataStatus

        # Force cache invalidation by clearing cache file
        src = get_weather_source()
        import os
        if os.path.exists(src._cache_file):
            try:
                os.remove(src._cache_file)
            except Exception:
                pass

        grid = await src.fetch()
        saved = await _persist_weather(grid, run_id)

        FreshnessRegistry.update("weather", status=DataStatus.NEAR_REAL_TIME,
                                 last_updated=datetime.now(timezone.utc),
                                 record_count=len(grid))
        return _finish_task(t, "success",
            records_received=len(grid), records_saved=saved,
            observation_time=datetime.now(timezone.utc),
            note=f"{len(grid)} grid points from Open-Meteo NWP")
    except Exception as e:
        FreshnessRegistry.update("weather", last_error=str(e), status=DataStatus.OFFLINE)
        return _finish_task(t, "failed", error=str(e))


async def _persist_weather(grid: List[Dict], run_id: str) -> int:
    if not grid:
        return 0
    saved = 0
    try:
        from app.database import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        retrieved = datetime.now(timezone.utc)
        try:
            for pt in grid:
                db.execute(text("""
                    INSERT INTO live_weather_observations
                      (id, retrieved_at, latitude, longitude,
                       wind_speed_ms, wind_direction_deg, air_temp_celsius,
                       sea_level_pressure_hpa, precipitation_mm, weather_code,
                       source, run_id)
                    VALUES
                      (uuid_generate_v4(), :retrieved, :lat, :lon,
                       :wind, :wind_dir, :temp, :pressure, :precip, :code,
                       :source, :run_id)
                """), {
                    "retrieved": retrieved,
                    "lat": pt["latitude"], "lon": pt["longitude"],
                    "wind": pt.get("wind_speed_ms"), "wind_dir": pt.get("wind_direction_deg"),
                    "temp": pt.get("air_temp_celsius"), "pressure": pt.get("sea_level_pressure_hpa"),
                    "precip": pt.get("precipitation_mm"), "code": pt.get("weather_code"),
                    "source": pt.get("source", "Open-Meteo"),
                    "run_id": run_id,
                })
                saved += 1
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.debug(f"[weather] DB persist failed (non-fatal): {e}")
    return saved


async def update_ocean(run_id: str) -> Dict:
    t = _task("ocean")
    try:
        from app.sources.ocean_source import get_ocean_source
        from app.core.freshness import FreshnessRegistry, DataStatus

        src = get_ocean_source()
        import os
        if os.path.exists(src._cache_file):
            try:
                os.remove(src._cache_file)
            except Exception:
                pass

        grid = await src.fetch()
        saved = await _persist_ocean(grid, run_id)

        FreshnessRegistry.update("ocean", status=DataStatus.NEAR_REAL_TIME,
                                 last_updated=datetime.now(timezone.utc),
                                 record_count=len(grid))
        return _finish_task(t, "success",
            records_received=len(grid), records_saved=saved,
            observation_time=datetime.now(timezone.utc),
            note=f"{len(grid)} grid points from Open-Meteo Marine")
    except Exception as e:
        FreshnessRegistry.update("ocean", last_error=str(e), status=DataStatus.OFFLINE)
        return _finish_task(t, "failed", error=str(e))


async def _persist_ocean(grid: List[Dict], run_id: str) -> int:
    if not grid:
        return 0
    saved = 0
    try:
        from app.database import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        retrieved = datetime.now(timezone.utc)
        try:
            for pt in grid:
                db.execute(text("""
                    INSERT INTO live_ocean_observations
                      (id, retrieved_at, latitude, longitude,
                       current_speed_ms, current_direction_deg,
                       current_u_ms, current_v_ms,
                       significant_wave_height_m, wave_period_s,
                       source, run_id)
                    VALUES
                      (uuid_generate_v4(), :retrieved, :lat, :lon,
                       :speed, :dir, :u, :v, :wave_h, :wave_p,
                       :source, :run_id)
                """), {
                    "retrieved": retrieved,
                    "lat": pt["latitude"], "lon": pt["longitude"],
                    "speed": pt.get("current_speed_ms"), "dir": pt.get("current_direction_deg"),
                    "u": pt.get("current_u_ms"), "v": pt.get("current_v_ms"),
                    "wave_h": pt.get("significant_wave_height_m"),
                    "wave_p": pt.get("wave_period_s"),
                    "source": pt.get("source", "Open-Meteo Marine"),
                    "run_id": run_id,
                })
                saved += 1
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.debug(f"[ocean] DB persist failed (non-fatal): {e}")
    return saved


async def update_vessels(run_id: str) -> Dict:
    t = _task("ais")
    try:
        from app.sources.vessel_source import get_vessel_service
        from app.core.freshness import FreshnessRegistry, DataStatus

        svc = get_vessel_service()
        if not settings.has_ais:
            FreshnessRegistry.update("ais", status=DataStatus.OFFLINE,
                                     last_error="AIS_PROVIDER and AIS_API_KEY not configured")
            return _finish_task(t, "skipped",
                note="No AIS credentials. Set AIS_PROVIDER and AIS_API_KEY.")

        provider = (settings.AIS_PROVIDER or "").lower()

        # AISStream uses WebSocket — start the stream task if not already running
        if provider == "aisstream":
            # Check if we already have a live position from the WS stream
            pos = svc.get_position()
            if pos.get("is_real"):
                obs_time = None
                ts = pos.get("timestamp")
                if ts:
                    try:
                        obs_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    except Exception:
                        pass
                FreshnessRegistry.update("ais", status=DataStatus.LIVE,
                                         last_updated=obs_time or datetime.now(timezone.utc))
                return _finish_task(t, "success",
                    records_received=1, records_saved=1,
                    observation_time=obs_time,
                    note=f"{pos.get('vessel_name','?')} @ {pos.get('latitude',0):.4f},{pos.get('longitude',0):.4f}")

            # No live position yet — ensure the WS listener is running
            _ensure_aisstream_running(svc)
            FreshnessRegistry.update("ais", status=DataStatus.OFFLINE,
                                     last_error="AISStream connected, waiting for position fix in Antarctic region")
            return _finish_task(t, "no_new_data",
                note="AISStream WebSocket connecting — waiting for vessel in Antarctic bounding box")

        # REST-based providers
        await svc.poll_once()
        pos = svc.get_position()
        if pos.get("is_real"):
            obs_time = None
            ts = pos.get("timestamp")
            if ts:
                try:
                    obs_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except Exception:
                    pass
            FreshnessRegistry.update("ais", status=DataStatus.LIVE,
                                     last_updated=obs_time or datetime.now(timezone.utc))
            return _finish_task(t, "success",
                records_received=1, records_saved=1,
                observation_time=obs_time,
                note=f"{pos.get('vessel_name','?')} @ {pos.get('latitude',0):.4f},{pos.get('longitude',0):.4f}")
        else:
            FreshnessRegistry.update("ais", status=DataStatus.OFFLINE,
                                     last_error="AIS poll returned no real position")
            return _finish_task(t, "failed",
                error="AIS provider returned no valid position",
                note="Check AIS_API_KEY and AIS_API_URL")
    except Exception as e:
        FreshnessRegistry.update("ais", last_error=str(e), status=DataStatus.OFFLINE)
        return _finish_task(t, "failed", error=str(e))


# ── AISStream WebSocket background task ───────────────────────────────────────

_aisstream_task: Optional[asyncio.Task] = None


def _ensure_aisstream_running(svc):
    """Start the AISStream WebSocket listener if not already running."""
    global _aisstream_task
    if _aisstream_task and not _aisstream_task.done():
        return  # already running

    async def _run_stream():
        from app.sources.vessel_source import AISStreamAdapter
        from app.core.freshness import FreshnessRegistry, DataStatus
        adapter = AISStreamAdapter()
        logger.info("[ais] Starting AISStream WebSocket listener for Antarctic region")
        retry_delay = 5
        while True:
            try:
                async for pos in adapter.stream():
                    svc.update_position(pos)
                    # Broadcast via live WebSocket
                    if _ws_broadcast_fn:
                        try:
                            await _ws_broadcast_fn({
                                "event": "VESSEL_UPDATED",
                                "source_id": "ais",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "position": pos.to_dict(),
                            })
                        except Exception:
                            pass
                retry_delay = 5  # reset on clean exit
            except Exception as e:
                logger.warning(f"[ais] Stream error, retrying in {retry_delay}s: {e}")
                FreshnessRegistry.update("ais", last_error=str(e), status=DataStatus.OFFLINE)
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 300)  # exponential backoff up to 5 min

    _aisstream_task = asyncio.create_task(_run_stream())


async def recalculate_risk(run_id: str) -> Dict:
    t = _task("risk")
    try:
        from app.services.risk_service import calculate_risk
        from app.schemas.routes import RiskCalculateRequest
        from app.sources.vessel_source import get_vessel_service

        svc = get_vessel_service()
        pos = svc.get_position()
        lat = pos.get("latitude", -65.0) if pos.get("is_real") else None

        if lat is None:
            return _finish_task(t, "skipped",
                note="No vessel position — risk calculated at default Antarctic waypoints")

        req = RiskCalculateRequest(latitude=lat,
                                   longitude=pos.get("longitude", 0.0), radius_km=100.0)
        risk = calculate_risk(req)
        return _finish_task(t, "success",
            records_saved=1,
            observation_time=datetime.now(timezone.utc),
            note=f"Risk: {risk['total_risk_score']*100:.0f}/100 ({risk['risk_category']})")
    except Exception as e:
        return _finish_task(t, "failed", error=str(e))


async def check_routes(run_id: str) -> Dict:
    t = _task("routes")
    try:
        from app.services.alert_service import AlertService, Alert, AlertLevel
        from app.services.risk_service import calculate_risk
        from app.schemas.routes import RiskCalculateRequest
        from app.sources.vessel_source import get_vessel_service

        svc = get_vessel_service()
        pos = svc.get_position()
        if not pos.get("is_real"):
            return _finish_task(t, "skipped", note="No real vessel position — skip route check")

        lat = pos["latitude"]
        lon = pos["longitude"]
        req = RiskCalculateRequest(latitude=lat, longitude=lon, radius_km=100.0)
        risk = calculate_risk(req)

        if risk["total_risk_score"] > 0.65:
            AlertService.add_alert(Alert(
                alert_type="ROUTE_UNSAFE",
                level=AlertLevel.DANGER,
                title="Route Risk Elevated",
                message=(
                    f"Navigation risk at vessel position: {risk['total_risk_score']*100:.0f}/100 "
                    f"({risk['risk_category'].upper()}). "
                    + (risk["recommendations"][0] if risk.get("recommendations") else "")
                ),
                data={"risk_score": risk["total_risk_score"],
                      "risk_category": risk["risk_category"],
                      "lat": lat, "lon": lon},
            ))
            return _finish_task(t, "success",
                note=f"⚠ Route risk: {risk['total_risk_score']*100:.0f}/100 — alert raised")
        return _finish_task(t, "success",
            note=f"Route safe. Risk: {risk['total_risk_score']*100:.0f}/100")
    except Exception as e:
        return _finish_task(t, "failed", error=str(e))


async def publish_updates(tasks: Dict[str, Dict], run_id: str):
    """Broadcast WebSocket events to all connected frontend clients."""
    if _ws_broadcast_fn is None:
        return

    # Build list of updated sources
    updated = [sid for sid, t in tasks.items() if t["status"] in ("success",)]
    failed  = [sid for sid, t in tasks.items() if t["status"] == "failed"]

    payload = {
        "event": "DATA_REFRESH_COMPLETE",
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sources_updated": updated,
        "sources_failed": failed,
        "tasks": tasks,
    }

    try:
        await _ws_broadcast_fn(payload)
        logger.info(f"[hourly] WebSocket broadcast: updated={updated} failed={failed}")
    except Exception as e:
        logger.warning(f"[hourly] WebSocket broadcast failed: {e}")

    # Individual typed events
    event_map = {
        "satellite": "SATELLITE_UPDATED",
        "sea_ice":   "SEA_ICE_UPDATED",
        "icebergs":  "ICEBERGS_UPDATED",
        "weather":   "WEATHER_UPDATED",
        "ocean":     "OCEAN_UPDATED",
        "ais":       "VESSEL_UPDATED",
        "risk":      "RISK_UPDATED",
        "routes":    "ROUTE_UPDATED",
    }
    for sid, event_name in event_map.items():
        if sid in updated:
            try:
                await _ws_broadcast_fn({
                    "event": event_name,
                    "source_id": sid,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "task": tasks.get(sid, {}),
                })
            except Exception:
                pass


# ── Main orchestrator ─────────────────────────────────────────────────────────

async def run_hourly_update(triggered_by: str = "scheduler"):
    """
    Main hourly update function. Runs all source updates sequentially
    and publishes results via WebSocket.

    Should not raise — all errors are captured per-task.
    """
    global _current_run, _run_history, _run_counter, _next_run_at

    _run_counter += 1
    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)

    logger.info("=" * 55)
    logger.info(f"[hourly] UPDATE RUN #{_run_counter} started ({triggered_by})")
    logger.info(f"[hourly] Run ID: {run_id}")
    logger.info("=" * 55)

    _current_run = {
        "run_id": run_id,
        "run_number": _run_counter,
        "started_at": started_at.isoformat(),
        "finished_at": None,
        "triggered_by": triggered_by,
        "status": "running",
        "tasks": {},
    }

    # ── Run all tasks ──────────────────────────────────────────────────────────
    tasks = {}

    async def run_task(name: str, coro):
        logger.info(f"[hourly]   → {name}")
        try:
            result = await coro
            tasks[name] = result
            status = result.get("status", "?")
            note = result.get("note") or result.get("error") or ""
            logger.info(f"[hourly]   ✓ {name}: {status}  {note[:80]}")
        except Exception as e:
            tasks[name] = _finish_task(_task(name), "failed", error=str(e))
            logger.error(f"[hourly]   ✗ {name}: {e}")

    await run_task("satellite", update_satellite(run_id))
    await run_task("sea_ice",   update_sea_ice(run_id))
    await run_task("icebergs",  update_icebergs(run_id))
    await run_task("weather",   update_weather(run_id))
    await run_task("ocean",     update_ocean(run_id))
    await run_task("ais",       update_vessels(run_id))
    await run_task("risk",      recalculate_risk(run_id))
    await run_task("routes",    check_routes(run_id))

    # ── Summarise ──────────────────────────────────────────────────────────────
    finished_at = datetime.now(timezone.utc)
    duration = (finished_at - started_at).total_seconds()

    succeeded = sum(1 for t in tasks.values() if t["status"] == "success")
    failed    = sum(1 for t in tasks.values() if t["status"] == "failed")
    skipped   = sum(1 for t in tasks.values() if t["status"] in ("skipped", "no_new_data"))

    overall = "success" if failed == 0 else ("partial" if succeeded > 0 else "failed")

    # Schedule next run
    interval = settings.UPDATE_INTERVAL_MINUTES
    _next_run_at = finished_at + timedelta(minutes=interval)

    run_record = {
        "run_id": run_id,
        "run_number": _run_counter,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_seconds": round(duration, 2),
        "triggered_by": triggered_by,
        "status": overall,
        "succeeded": succeeded,
        "failed": failed,
        "skipped": skipped,
        "next_run_at": _next_run_at.isoformat(),
        "tasks": tasks,
    }

    _current_run = run_record
    _run_history.append(run_record)
    if len(_run_history) > 48:            # keep 48 runs (2 days at 1h intervals)
        _run_history = _run_history[-48:]

    # ── Persist run to DB ──────────────────────────────────────────────────────
    await _persist_run(run_record, run_id)

    logger.info(f"[hourly] RUN #{_run_counter} COMPLETE in {duration:.1f}s — "
                f"{succeeded} ok / {failed} failed / {skipped} skipped")
    logger.info(f"[hourly] Next update at: {_next_run_at.strftime('%Y-%m-%d %H:%M UTC')}")

    # ── Broadcast ─────────────────────────────────────────────────────────────
    await publish_updates(tasks, run_id)

    return run_record


async def _persist_run(record: Dict, run_id: str):
    """Write run summary to data_update_runs table."""
    try:
        from app.database import SessionLocal
        from sqlalchemy import text
        import json
        db = SessionLocal()
        try:
            db.execute(text("""
                INSERT INTO data_update_runs
                  (id, run_number, started_at, finished_at, duration_seconds,
                   triggered_by, overall_status, sources_attempted, sources_succeeded,
                   sources_failed, summary, next_run_at)
                VALUES
                  (:id, :run_num, :started, :finished, :duration,
                   :triggered, :status, :attempted, :succeeded, :failed,
                   :summary, :next_run)
            """), {
                "id": run_id,
                "run_num": record["run_number"],
                "started": record["started_at"],
                "finished": record["finished_at"],
                "duration": record["duration_seconds"],
                "triggered": record["triggered_by"],
                "status": record["status"],
                "attempted": record["succeeded"] + record["failed"] + record["skipped"],
                "succeeded": record["succeeded"],
                "failed": record["failed"],
                "summary": json.dumps({k: v.get("status") for k, v in record["tasks"].items()}),
                "next_run": record["next_run_at"],
            })
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.debug(f"[hourly] DB run persist failed (non-fatal): {e}")


# ── Changes diff (what changed since last run) ────────────────────────────────

def compute_changes() -> Dict:
    """
    Compare the last two completed runs and return a human-readable diff.
    Used by /api/live/changes and the AI Navigator's 'what changed' feature.
    """
    if len(_run_history) < 1:
        return {"changes": [], "last_run": None, "previous_run": None}

    last = _run_history[-1]
    prev = _run_history[-2] if len(_run_history) >= 2 else None

    changes = []
    for source_id, task in last.get("tasks", {}).items():
        status = task.get("status", "unknown")
        note = task.get("note", "")
        if status == "success":
            changes.append({
                "source_id": source_id,
                "type": "updated",
                "message": note or f"{source_id} updated",
                "observation_time": task.get("observation_time"),
                "records": task.get("records_saved", 0),
            })
        elif status == "failed":
            changes.append({
                "source_id": source_id,
                "type": "error",
                "message": f"{source_id} failed: {task.get('error','unknown error')}",
                "observation_time": None,
                "records": 0,
            })
        elif status == "no_new_data":
            changes.append({
                "source_id": source_id,
                "type": "no_change",
                "message": note or f"No new {source_id} data",
                "observation_time": task.get("observation_time"),
                "records": 0,
            })

    return {
        "changes": changes,
        "last_run": last.get("started_at"),
        "last_run_duration": last.get("duration_seconds"),
        "previous_run": prev.get("started_at") if prev else None,
        "next_run": _next_run_at.isoformat() if _next_run_at else None,
    }
