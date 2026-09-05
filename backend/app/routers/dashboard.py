from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.services import demo_service
from app.core.freshness import FreshnessRegistry
from app.config import settings

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard(db: Session = Depends(get_db)):
    """Main dashboard stats — enriched with real data where available."""
    data = demo_service.get_dashboard_stats()

    # Enrich with real sea ice
    try:
        from app.services.sea_ice_service import get_current_sea_ice
        ice = get_current_sea_ice("low")
        data["sea_ice_coverage_pct"] = ice["coverage_pct"]
        data["sea_ice_extent_km2"] = ice.get("extent_km2", data.get("sea_ice_extent_km2", 0))
    except Exception:
        pass

    # Enrich with real weather
    try:
        from app.services.weather_service import get_current_weather
        wx = get_current_weather()
        data["avg_wind_speed_ms"] = wx["avg_wind_speed_ms"]
    except Exception:
        pass

    # Enrich with real icebergs count
    try:
        from app.services.iceberg_service import list_icebergs
        ibs = list_icebergs()
        data["active_icebergs"] = ibs["total_count"]
        data["high_risk_icebergs"] = ibs["high_risk_count"]
    except Exception:
        pass

    # Vessel position
    try:
        from app.sources.vessel_source import get_vessel_service
        svc = get_vessel_service()
        pos = svc.get_position()
        data["vessel_lat"] = pos["latitude"]
        data["vessel_lon"] = pos["longitude"]
        data["vessel_speed_knots"] = pos["speed_knots"]
        data["vessel_heading_deg"] = pos["heading_deg"]
        data["vessel_status"] = pos["navigation_status"]
        data["vessel_data_mode"] = pos["data_mode"]
        data["vessel_name"] = pos["vessel_name"]
    except Exception:
        data["vessel_data_mode"] = "demo"

    # System freshness summary
    data["system_status"] = FreshnessRegistry.summary()
    data["effective_data_mode"] = settings.effective_data_mode

    # Alert count
    try:
        from app.services.alert_service import AlertService
        data["unread_alerts"] = AlertService.get_unread_count()
    except Exception:
        data["unread_alerts"] = 0

    return data
