"""Ocean service — uses Open-Meteo Marine when available, demo fallback."""
from app.services import demo_service
from app.core.freshness import FreshnessRegistry


def _freshness_tag(is_real: bool) -> dict:
    f = FreshnessRegistry.get("ocean")
    return {"freshness": f.to_dict() if f else None, "is_real": is_real,
            "data_mode": "live" if is_real else "demo"}


def get_current_ocean():
    try:
        from app.sources.ocean_source import get_ocean_source
        grid = get_ocean_source().get_grid()
        if grid:
            avg_speed = sum(p["current_speed_ms"] for p in grid) / len(grid)
            sst_vals = [p["sea_surface_temp_celsius"] for p in grid if p.get("sea_surface_temp_celsius")]
            avg_sst = sum(sst_vals) / len(sst_vals) if sst_vals else None
            result = {
                "timestamp": grid[0].get("observation_time"),
                "grid_points": grid,
                "avg_current_speed_ms": round(avg_speed, 3),
                "avg_sst_celsius": round(avg_sst, 1) if avg_sst else None,
            }
            result.update(_freshness_tag(True))
            return result
    except Exception:
        pass
    result = demo_service.get_ocean()
    result.update(_freshness_tag(False))
    return result


def get_nearest(lat: float, lon: float):
    """Get ocean conditions at a specific lat/lon."""
    try:
        from app.sources.ocean_source import get_ocean_source
        pt = get_ocean_source().get_nearest(lat, lon)
        if pt:
            return {**pt, **_freshness_tag(True)}
    except Exception:
        pass
    import math
    grid = demo_service.get_ocean()["grid_points"]
    nearest = min(grid, key=lambda p: math.sqrt((p["latitude"] - lat) ** 2 + (p["longitude"] - lon) ** 2))
    return {**nearest, **_freshness_tag(False)}
