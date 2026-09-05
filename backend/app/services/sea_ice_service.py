"""
Sea ice service — uses real NSIDC data when available, demo fallback.
"""
from app.config import settings
from app.services import demo_service
from app.schemas.sea_ice import SeaIcePredictRequest
from app.core.freshness import FreshnessRegistry
from datetime import datetime, timezone


def _use_real() -> bool:
    """True when real source has data, False → use demo."""
    try:
        from app.sources.sea_ice_source import get_sea_ice_source
        src = get_sea_ice_source()
        if src.get_latest_extent() is not None:
            return True
    except Exception:
        pass
    return False


def _freshness_tag(is_real: bool) -> dict:
    f = FreshnessRegistry.get("sea_ice")
    return {
        "freshness": f.to_dict() if f else None,
        "is_real": is_real,
        "data_mode": "live" if is_real else "demo",
    }


def get_current_sea_ice(resolution: str = "low"):
    """Current SIC grid — real NSIDC monthly extent + demo spatial grid."""
    is_real = _use_real()
    result = demo_service.get_sea_ice_grid(resolution)

    if is_real:
        # Enrich coverage_pct from real NSIDC extent
        try:
            from app.sources.sea_ice_source import get_sea_ice_source
            latest = get_sea_ice_source().get_latest_extent()
            if latest:
                result["coverage_pct"] = round(latest["coverage_pct"], 1)
                result["extent_km2"] = round(latest["extent_km2"], 0)
                result["source"] = latest.get("source", "NSIDC")
                result["data_mode"] = "live"
                result["is_real"] = True
        except Exception:
            pass

    result.update(_freshness_tag(is_real))
    return result


def get_history(days: int = 90):
    """Historical SIC time-series — real NSIDC daily CSV when available."""
    is_real = _use_real()

    if is_real:
        try:
            from app.sources.sea_ice_source import get_sea_ice_source
            records = get_sea_ice_source().get_history(days=days)
            if records:
                result = {
                    "start_date": records[0]["date"],
                    "end_date": records[-1]["date"],
                    "data_points": records,
                    "source": "NSIDC Sea Ice Index G02135 v3",
                }
                result.update(_freshness_tag(True))
                return result
        except Exception:
            pass

    result = demo_service.get_sea_ice_history(days)
    result.update(_freshness_tag(False))
    return result


def get_forecast(horizon_hours: int = 72):
    forecasts = demo_service.get_sea_ice_forecast(horizon_hours)
    target = next((f for f in forecasts if f["horizon_hours"] == horizon_hours), forecasts[-1])
    f_tag = _freshness_tag(_use_real())
    target.update(f_tag)
    return target


def predict(request: SeaIcePredictRequest):
    return demo_service.get_sea_ice_forecast(request.horizon_hours)
