"""
POLAR-AI Agent Tools
10 tools for the Polar Navigator to query real application data.
"""
from app.services import (
    demo_service, sea_ice_service, iceberg_service,
    weather_service, ocean_service, risk_service, route_service
)
from app.schemas.routes import RiskCalculateRequest, RouteCompareRequest


def get_current_ice_conditions(lat: float = -65.0, lon: float = -60.0) -> dict:
    """Get current sea-ice conditions at a location."""
    sic = demo_service._sic_at(lat, lon)
    category = demo_service._ice_category(sic)
    grid = demo_service.get_sea_ice_grid("low")
    return {
        "location": {"lat": lat, "lon": lon},
        "sea_ice_concentration": round(sic, 3),
        "ice_category": category,
        "coverage_pct": grid["coverage_pct"],
        "data_mode": "demo",
    }


def get_sea_ice_forecast(horizon_hours: int = 72) -> dict:
    """Get sea-ice forecast for given horizon."""
    forecasts = demo_service.get_sea_ice_forecast(horizon_hours)
    return forecasts[-1] if forecasts else {}


def get_icebergs(limit: int = 5) -> dict:
    """Get list of active icebergs with risk levels."""
    result = demo_service.get_icebergs()
    result["icebergs"] = result["icebergs"][:limit]
    return result


def get_iceberg_trajectory(iceberg_name: str) -> dict:
    """Get predicted trajectory for a named iceberg."""
    return demo_service.get_iceberg_trajectory(iceberg_name, horizon_hours=72) or {}


def get_weather(lat: float = -65.0, lon: float = -60.0) -> dict:
    """Get current weather conditions at a location."""
    weather = demo_service.get_weather()
    # Find nearest grid point
    import math
    nearest = min(
        weather["grid_points"],
        key=lambda p: math.sqrt((p["latitude"] - lat)**2 + (p["longitude"] - lon)**2)
    )
    return {
        "location": {"lat": lat, "lon": lon},
        "wind_speed_ms": nearest["wind_speed_ms"],
        "wind_direction_deg": nearest["wind_direction_deg"],
        "air_temp_celsius": nearest["air_temp_celsius"],
        "weather_risk_score": nearest["weather_risk_score"],
        "data_mode": "demo",
    }


def get_ocean_conditions(lat: float = -65.0, lon: float = -60.0) -> dict:
    """Get ocean conditions at a location."""
    ocean = demo_service.get_ocean()
    import math
    nearest = min(
        ocean["grid_points"],
        key=lambda p: math.sqrt((p["latitude"] - lat)**2 + (p["longitude"] - lon)**2)
    )
    return {
        "location": {"lat": lat, "lon": lon},
        "current_speed_ms": nearest["current_speed_ms"],
        "current_direction_deg": nearest["current_direction_deg"],
        "sea_surface_temp_celsius": nearest["sea_surface_temp_celsius"],
        "significant_wave_height_m": nearest.get("significant_wave_height_m"),
        "ocean_risk_score": nearest["ocean_risk_score"],
        "data_mode": "demo",
    }


def calculate_navigation_risk(lat: float, lon: float, radius_km: float = 50.0) -> dict:
    """Calculate navigation risk at a location."""
    req = RiskCalculateRequest(latitude=lat, longitude=lon, radius_km=radius_km)
    return risk_service.calculate_risk(req)


def generate_routes(origin_lat: float, origin_lon: float,
                    dest_lat: float, dest_lon: float) -> dict:
    """Generate all route types between two points."""
    req = RouteCompareRequest(
        origin_lat=origin_lat, origin_lon=origin_lon,
        destination_lat=dest_lat, destination_lon=dest_lon,
    )
    return route_service.compare_routes(req)


def compare_routes(origin_lat: float, origin_lon: float,
                   dest_lat: float, dest_lon: float) -> dict:
    """Compare all available routes and get recommendation."""
    return generate_routes(origin_lat, origin_lon, dest_lat, dest_lon)


def get_vessel_status() -> dict:
    """Get current vessel status."""
    dashboard = demo_service.get_dashboard_stats()
    return {
        "vessel_name": "RV Polar Explorer",
        "latitude": dashboard["vessel_lat"],
        "longitude": dashboard["vessel_lon"],
        "speed_knots": dashboard["vessel_speed_knots"],
        "heading_deg": dashboard["vessel_heading_deg"],
        "status": dashboard["vessel_status"],
        "current_risk": dashboard["current_risk_score"],
        "data_mode": "demo",
    }


# Tool registry
TOOLS = {
    "get_current_ice_conditions": get_current_ice_conditions,
    "get_sea_ice_forecast": get_sea_ice_forecast,
    "get_icebergs": get_icebergs,
    "get_iceberg_trajectory": get_iceberg_trajectory,
    "get_weather": get_weather,
    "get_ocean_conditions": get_ocean_conditions,
    "calculate_navigation_risk": calculate_navigation_risk,
    "generate_routes": generate_routes,
    "compare_routes": compare_routes,
    "get_vessel_status": get_vessel_status,
}
