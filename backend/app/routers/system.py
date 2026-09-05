"""System status endpoint — comprehensive data-source freshness."""
from fastapi import APIRouter
from app.core.freshness import FreshnessRegistry
from app.database import check_db_connection, check_postgis
from app.config import settings
from datetime import datetime, timezone

router = APIRouter()


@router.get("/system/status")
async def get_system_status():
    """
    Returns comprehensive status of all data sources with freshness info.
    Frontend uses this to display the live system-status panel.
    """
    # Update DB status
    db_ok = check_db_connection()
    from app.core.freshness import DataStatus
    FreshnessRegistry.update(
        "database",
        status=DataStatus.NEAR_REAL_TIME if db_ok else DataStatus.OFFLINE,
        last_updated=datetime.now(timezone.utc) if db_ok else None,
    )

    summary = FreshnessRegistry.summary()
    summary["effective_data_mode"] = settings.effective_data_mode
    summary["app_version"] = settings.APP_VERSION
    summary["scheduler_enabled"] = settings.SCHEDULER_ENABLED
    summary["credentials"] = {
        "copernicus": settings.has_copernicus,
        "earthdata": settings.has_earthdata,
        "cds": settings.has_cds,
        "cmems": settings.has_cmems,
        "ais": settings.has_ais,
        "llm": settings.has_llm,
        "llm_provider": settings.llm_provider,
    }
    return summary
