"""Weather service — uses Open-Meteo when available, demo fallback."""
from app.services import demo_service
from app.core.freshness import FreshnessRegistry


def _freshness_tag(is_real: bool) -> dict:
    f = FreshnessRegistry.get("weather")
    return {"freshness": f.to_dict() if f else None, "is_real": is_real,
            "data_mode": "live" if is_real else "demo"}


def get_current_weather():
    try:
        from app.sources.weather_source import get_weather_source
        grid = get_weather_source().get_grid()
        if grid:
            avg_wind = sum(p["wind_speed_ms"] for p in grid) / len(grid)
            min_temp = min(p["air_temp_celsius"] for p in grid)
            result = {
                "timestamp": grid[0].get("observation_time"),
                "grid_points": grid,
                "avg_wind_speed_ms": round(avg_wind, 2),
                "min_temp_celsius": round(min_temp, 1),
            }
            result.update(_freshness_tag(True))
            return result
    except Exception:
        pass
    result = demo_service.get_weather(t_offset_hours=0)
    result.update(_freshness_tag(False))
    return result


def get_forecast(horizon_hours: int = 72):
    result = demo_service.get_weather_forecast(horizon_hours)
    result.update(_freshness_tag(False))
    return result


def get_nearest(lat: float, lon: float):
    """Get weather at a specific lat/lon (nearest grid point)."""
    try:
        from app.sources.weather_source import get_weather_source
        pt = get_weather_source().get_nearest(lat, lon)
        if pt:
            return {**pt, **_freshness_tag(True)}
    except Exception:
        pass
    import math
    grid = demo_service.get_weather()["grid_points"]
    nearest = min(grid, key=lambda p: math.sqrt((p["latitude"] - lat) ** 2 + (p["longitude"] - lon) ** 2))
    return {**nearest, **_freshness_tag(False)}
