"""
POLAR-AI Background Scheduler
==============================
Runs the hourly update orchestrator on a configurable interval.
Interval is read from settings.UPDATE_INTERVAL_MINUTES (default 60).
The scheduler runs independently of the browser — closing the UI does NOT stop updates.
"""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from typing import Optional, Any
from loguru import logger

from app.config import settings

_scheduler: Optional[Any] = None

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    HAS_APSCHEDULER = True
except ImportError:
    HAS_APSCHEDULER = False


async def _run_hourly():
    """APScheduler job — delegates to the hourly update orchestrator."""
    try:
        from app.services.hourly_update_service import run_hourly_update
        await run_hourly_update(triggered_by="scheduler")
    except Exception as e:
        logger.error(f"[scheduler] Hourly update job failed: {e}")


def start_scheduler():
    global _scheduler

    if not HAS_APSCHEDULER:
        logger.warning(
            "[scheduler] APScheduler not installed — background updates disabled.\n"
            "  Install with: pip install apscheduler"
        )
        return

    if not settings.SCHEDULER_ENABLED:
        logger.info("[scheduler] Disabled via SCHEDULER_ENABLED=false")
        return

    if _scheduler and _scheduler.running:
        logger.info("[scheduler] Already running")
        return

    interval = max(1, settings.UPDATE_INTERVAL_MINUTES)   # minimum 1 minute
    _scheduler = AsyncIOScheduler(timezone="UTC")

    # Main hourly update — the ONLY recurring job now
    # (individual source jobs removed — the orchestrator handles all of them)
    _scheduler.add_job(
        _run_hourly,
        IntervalTrigger(minutes=interval),
        id="hourly_update",
        # Do NOT set next_run_time here — startup sync runs separately via asyncio.create_task
        max_instances=1,           # never run two overlapping updates
        coalesce=True,             # skip missed runs
    )

    _scheduler.start()
    logger.info(
        f"[scheduler] Started — updates every {interval} minute(s). "
        f"First scheduled run in {interval} min."
    )


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[scheduler] Stopped")
    _scheduler = None
