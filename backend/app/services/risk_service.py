"""
POLAR-AI Risk Engine
Calculates multi-factor navigation risk scores.

Risk Formula:
  Total = W1 * SeaIceRisk + W2 * IcebergRisk + W3 * WeatherRisk + W4 * OceanRisk

Weights are configurable (defaults: 0.35, 0.30, 0.20, 0.15).
"""
import math
import numpy as np
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from app.services import demo_service
from app.schemas.routes import RiskCalculateRequest, RiskCalculateResponse


DEFAULT_WEIGHTS = {
    "sea_ice": 0.35,
    "iceberg": 0.30,
    "weather": 0.20,
    "ocean": 0.15,
}


def _risk_category(score: float) -> str:
    if score < 0.25:
        return "low"
    elif score < 0.50:
        return "moderate"
    elif score < 0.75:
        return "high"
    else:
        return "extreme"


def calculate_sea_ice_risk(lat: float, lon: float, radius_km: float = 50.0) -> Dict:
    """Calculate sea-ice risk at a location."""
    sic = demo_service._sic_at(lat, lon)
    category = demo_service._ice_category(sic)

    # Risk increases sharply above 15% concentration
    if sic < 0.15:
        risk = 0.0
    elif sic < 0.40:
        risk = (sic - 0.15) / 0.25 * 0.3
    elif sic < 0.65:
        risk = 0.3 + (sic - 0.40) / 0.25 * 0.4
    elif sic < 0.85:
        risk = 0.7 + (sic - 0.65) / 0.20 * 0.25
    else:
        risk = 0.95

    factors = []
    if sic > 0.80:
        factors.append(f"Consolidated ice ({sic*100:.0f}% concentration) — vessel may become beset")
    elif sic > 0.60:
        factors.append(f"High sea-ice concentration ({sic*100:.0f}%) — significantly reduced speed")
    elif sic > 0.40:
        factors.append(f"Moderate sea-ice ({sic*100:.0f}%) — reduced maneuverability")
    elif sic > 0.15:
        factors.append(f"Low sea-ice ({sic*100:.0f}%) — minor hazard")
    else:
        factors.append(f"Open water — negligible ice risk")

    return {
        "score": float(np.clip(risk, 0, 1)),
        "sic": sic,
        "category": category,
        "factors": factors,
    }


def calculate_iceberg_risk(lat: float, lon: float, radius_km: float = 100.0) -> Dict:
    """Calculate iceberg risk near a location."""
    icebergs = demo_service.get_icebergs()["icebergs"]
    nearby = []
    for iceberg in icebergs:
        dist = demo_service.haversine_km(lat, lon, iceberg["latitude"], iceberg["longitude"])
        if dist <= radius_km:
            nearby.append({"iceberg": iceberg, "distance_km": dist})

    if not nearby:
        return {"score": 0.0, "nearby_count": 0, "closest_km": None, "factors": ["No icebergs within radius"]}

    # Risk depends on proximity and iceberg size
    max_risk = 0.0
    factors = []
    closest_km = min(n["distance_km"] for n in nearby)

    for n in nearby:
        dist = n["distance_km"]
        iceberg = n["iceberg"]
        area = iceberg.get("area_km2", 100)

        # Proximity risk (inverse distance)
        proximity_risk = max(0, 1 - dist / radius_km)
        # Size multiplier
        size_factor = min(1.0, area / 1000.0)
        # Check if iceberg trajectory intersects route
        trajectory_risk = 0.2 if iceberg["risk_level"] == "high" else 0.1

        iceberg_risk = float(np.clip(proximity_risk * 0.6 + size_factor * 0.3 + trajectory_risk, 0, 1))
        if iceberg_risk > max_risk:
            max_risk = iceberg_risk

        if dist < 20:
            factors.append(f"Iceberg {iceberg['iceberg_name']} is {dist:.1f} km away — IMMEDIATE DANGER")
        elif dist < 50:
            factors.append(f"Iceberg {iceberg['iceberg_name']} ({iceberg['length_km']:.0f} km long) is {dist:.1f} km away")
        else:
            factors.append(f"Iceberg {iceberg['iceberg_name']} is {dist:.1f} km — monitoring recommended")

    if not factors:
        factors.append("No significant iceberg hazard detected")

    return {
        "score": float(np.clip(max_risk, 0, 1)),
        "nearby_count": len(nearby),
        "closest_km": round(closest_km, 1),
        "factors": factors,
    }


def calculate_weather_risk(lat: float, lon: float) -> Dict:
    """Calculate weather-based navigation risk."""
    seed = int(abs(lat * 100 + lon * 100)) % 99991
    rng = np.random.default_rng(seed)

    wind_speed = float(rng.uniform(5, 18))
    wind_dir = float(rng.uniform(0, 360))
    wave_h = float(rng.uniform(1.5, 5.0))

    # WMO wind scale risk
    if wind_speed < 8:
        wind_risk = 0.1
    elif wind_speed < 12:
        wind_risk = 0.3
    elif wind_speed < 16:
        wind_risk = 0.6
    else:
        wind_risk = 0.85

    # Wave height risk
    if wave_h < 2.0:
        wave_risk = 0.1
    elif wave_h < 3.5:
        wave_risk = 0.35
    elif wave_h < 5.0:
        wave_risk = 0.65
    else:
        wave_risk = 0.90

    score = float(np.clip(0.6 * wind_risk + 0.4 * wave_risk, 0, 1))

    factors = [f"Wind: {wind_speed:.1f} m/s from {wind_dir:.0f}°"]
    if wind_speed > 15:
        factors.append("Storm-force winds — dangerous navigation conditions")
    elif wind_speed > 10:
        factors.append("Strong winds — reduced visibility and vessel stability")
    factors.append(f"Wave height: {wave_h:.1f} m")
    if wave_h > 4:
        factors.append("Very rough seas — risk of cargo/equipment damage")

    return {
        "score": score,
        "wind_speed_ms": wind_speed,
        "wind_direction_deg": wind_dir,
        "wave_height_m": wave_h,
        "factors": factors,
    }


def calculate_ocean_risk(lat: float, lon: float) -> Dict:
    """Calculate ocean-current risk."""
    seed = int(abs(lat * 200 + lon * 200)) % 99991
    rng = np.random.default_rng(seed)

    current_u = float(rng.uniform(0.05, 0.45))
    current_v = float(rng.normal(0, 0.15))
    current_speed = math.sqrt(current_u**2 + current_v**2)
    sst = float(8 - 10 * (abs(lat) - 55) / 25 + rng.normal(0, 1))

    if current_speed < 0.15:
        score = 0.1
    elif current_speed < 0.30:
        score = 0.25
    elif current_speed < 0.45:
        score = 0.50
    else:
        score = 0.75

    factors = [f"Ocean current: {current_speed:.3f} m/s"]
    if current_speed > 0.4:
        factors.append("Strong ACC current — significant fuel penalty expected")
    if sst < -1.5:
        factors.append("Sub-freezing SST — risk of sea spray icing on vessel")
    factors.append(f"SST: {sst:.1f}°C")

    return {
        "score": float(np.clip(score, 0, 1)),
        "current_speed_ms": round(current_speed, 3),
        "sst_celsius": round(sst, 1),
        "factors": factors,
    }


def calculate_risk(request: RiskCalculateRequest) -> Dict:
    """Full multi-factor risk calculation for a location."""
    weights = request.weights or DEFAULT_WEIGHTS

    # Ensure weights sum to 1.0
    total_w = sum(weights.values())
    if abs(total_w - 1.0) > 0.01:
        weights = {k: v / total_w for k, v in weights.items()}

    ice_result = calculate_sea_ice_risk(request.latitude, request.longitude, request.radius_km)
    iceberg_result = calculate_iceberg_risk(request.latitude, request.longitude, request.radius_km)
    weather_result = calculate_weather_risk(request.latitude, request.longitude)
    ocean_result = calculate_ocean_risk(request.latitude, request.longitude)

    w_ice = weights.get("sea_ice", 0.35)
    w_ib = weights.get("iceberg", 0.30)
    w_wx = weights.get("weather", 0.20)
    w_oc = weights.get("ocean", 0.15)

    total = (
        w_ice * ice_result["score"] +
        w_ib * iceberg_result["score"] +
        w_wx * weather_result["score"] +
        w_oc * ocean_result["score"]
    )
    total = float(np.clip(total, 0, 1))

    all_factors = []
    for factor_list in [ice_result["factors"], iceberg_result["factors"],
                        weather_result["factors"], ocean_result["factors"]]:
        all_factors.extend([{"text": f, "source": "calculated"} for f in factor_list])

    recommendations = []
    if ice_result["score"] > 0.7:
        recommendations.append("Avoid this region — consolidated sea ice may beset vessel")
    if iceberg_result["score"] > 0.6:
        recommendations.append("Iceberg collision risk — post additional lookouts and reduce speed")
    if weather_result["score"] > 0.6:
        recommendations.append("Storm conditions expected — consider delaying transit or seeking shelter")
    if ocean_result["score"] > 0.5:
        recommendations.append("Strong currents — expect increased fuel consumption and course correction")
    if not recommendations:
        recommendations.append("Conditions acceptable for navigation with standard precautions")

    return {
        "latitude": request.latitude,
        "longitude": request.longitude,
        "radius_km": request.radius_km,
        "assessed_at": datetime.now(timezone.utc).isoformat(),
        "sea_ice_risk": round(ice_result["score"], 3),
        "iceberg_risk": round(iceberg_result["score"], 3),
        "weather_risk": round(weather_result["score"], 3),
        "ocean_risk": round(ocean_result["score"], 3),
        "total_risk_score": round(total, 3),
        "risk_category": _risk_category(total),
        "risk_factors": all_factors,
        "recommendations": recommendations,
        "data_mode": "demo",
    }
