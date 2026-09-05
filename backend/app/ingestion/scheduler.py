"""
POLAR-AI Background Scheduler
==============================
Runs scheduled data ingestion jobs using APScheduler.
Never hammers external APIs — respects update frequencies and caching.

Job schedule:
  AIS polling       → every 30s (when provider configured)
  Weather update    → every 30min
  Ocean update      → every 30min
  Iceberg update    → every 6h
  Sea ice update    → every 6h
  Satellite search  → every 30min
  Route safety check→ every 5min
"""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from typing import Optional

from loguru import logger

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    HAS_APSCHEDULER = True
except ImportError:
    HAS_APSCHEDULER = False

from app.config import settings

_scheduler: Optional[Any] = None


async def _job_weather():
    """Refresh weather grid from Open-Meteo."""
    try:
        from app.sources.weather_source import get_weather_source
        source = get_weather_source()
        result = await source.fetch()
        if result:
            logger.info(f"[scheduler] Weather: {len(result)} points updated")
    except Exception as e:
        logger.error(f"[scheduler] Weather job failed: {e}")


async def _job_ocean():
    """Refresh ocean grid from Open-Meteo Marine."""
    try:
        from app.sources.ocean_source import get_ocean_source
        source = get_ocean_source()
        result = await source.fetch()
        if result:
            logger.info(f"[scheduler] Ocean: {len(result)} points updated")
    except Exception as e:
        logger.error(f"[scheduler] Ocean job failed: {e}")


async def _job_icebergs():
    """Refresh iceberg data from NIC."""
    try:
        from app.sources.iceberg_source import get_iceberg_source
        source = get_iceberg_source()
        result = await source.fetch()
        if result:
            logger.info(f"[scheduler] Icebergs: {len(result)} records updated")
    except Exception as e:
        logger.error(f"[scheduler] Iceberg job failed: {e}")


async def _job_sea_ice():
    """Refresh sea ice data from NSIDC."""
    try:
        from app.sources.sea_ice_source import get_sea_ice_source
        source = get_sea_ice_source()
        result = await source.fetch()
        if result:
            logger.info("[scheduler] Sea ice data updated")
    except Exception as e:
        logger.error(f"[scheduler] Sea ice job failed: {e}")


async def _job_satellite():
    """Search for new Sentinel-1 products."""
    if not settings.has_copernicus:
        return
    try:
        from app.sources.satellite_source import get_satellite_source
        source = get_satellite_source()
        result = await source.fetch()
        if result:
            logger.info(f"[scheduler] Satellite: {len(result)} products found")
    except Exception as e:
        logger.error(f"[scheduler] Satellite job failed: {e}")


async def _job_ais_poll():
    """Poll AIS REST endpoint if provider is configured."""
    if not settings.has_ais:
        return
    # WebSocket providers handle themselves; only poll REST providers
    if settings.AIS_PROVIDER.lower() == "aisstream":
        return  # WebSocket, handled separately
    try:
        from app.sources.vessel_source import get_vessel_service
        svc = get_vessel_service()
        await svc.poll_once()
    except Exception as e:
        logger.error(f"[scheduler] AIS poll failed: {e}")


async def _job_route_safety_check():
    """Check if current route is still safe given updated conditions."""
    try:
        from app.services.alert_service import check_route_safety
        await check_route_safety()
    except Exception as e:
        logger.debug(f"[scheduler] Route safety check: {e}")


def start_scheduler():
    """Start the APScheduler background scheduler."""
    global _scheduler

    if not HAS_APSCHEDULER:
        logger.warning("[scheduler] APScheduler not installed — background jobs disabled")
        logger.warning("[scheduler] Install with: pip install apscheduler")
        return

    if not settings.SCHEDULER_ENABLED:
        logger.info("[scheduler] Scheduler disabled via SCHEDULER_ENABLED=false")
        return

    _scheduler = AsyncIOScheduler(timezone="UTC")

    # Weather — every 30 minutes
    _scheduler.add_job(_job_weather, IntervalTrigger(minutes=30), id="weather",
                       next_run_time=datetime.now(timezone.utc))

    # Ocean — every 30 minutes
    _scheduler.add_job(_job_ocean, IntervalTrigger(minutes=30), id="ocean",
                       next_run_time=datetime.now(timezone.utc))

    # Icebergs — every 6 hours
    _scheduler.add_job(_job_icebergs, IntervalTrigger(hours=6), id="icebergs",
                       next_run_time=datetime.now(timezone.utc))

    # Sea ice — every 6 hours
    _scheduler.add_job(_job_sea_ice, IntervalTrigger(hours=6), id="sea_ice",
                       next_run_time=datetime.now(timezone.utc))

    # Satellite — every 30 minutes (only runs if credentials present)
    _scheduler.add_job(_job_satellite, IntervalTrigger(minutes=30), id="satellite",
                       next_run_time=datetime.now(timezone.utc))

    # AIS REST poll — every 30 seconds
    _scheduler.add_job(_job_ais_poll, IntervalTrigger(seconds=30), id="ais_poll")

    # Route safety check — every 5 minutes
    _scheduler.add_job(_job_route_safety_check, IntervalTrigger(minutes=5), id="route_safety")

    _scheduler.start()
    logger.info("[scheduler] Background scheduler started with 7 jobs")


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[scheduler] Scheduler stopped")


# Make Optional[Any] work
from typing import Any
