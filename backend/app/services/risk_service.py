"""
POLAR-AI Risk Engine v2
========================
Uses REAL data from live sources in LIVE mode.
Falls back to physics model only when real data is unavailable.

Risk Formula:
  Total = 0.35*SeaIce + 0.30*Iceberg + 0.20*Weather + 0.15*Ocean
"""
from __future__ import annotations
import math
import numpy as np
from datetime import datetime, timezone
from typing import List, Dict, Optional
from app.schemas.routes import RiskCalculateRequest

DEFAULT_WEIGHTS = {"sea_ice": 0.35, "iceberg": 0.30, "weather": 0.20, "ocean": 0.15}


def _risk_category(score: float) -> str:
    if score < 0.25:   return "low"
    elif score < 0.50: return "moderate"
    elif score < 0.75: return "high"
    else:              return "extreme"


def _sic_to_risk(sic: float) -> float:
    if sic < 0.15:   return 0.0
    elif sic < 0.40: return (sic - 0.15) / 0.25 * 0.30
    elif sic < 0.65: return 0.30 + (sic - 0.40) / 0.25 * 0.40
    elif sic < 0.85: return 0.70 + (sic - 0.65) / 0.20 * 0.25
    else:            return 0.95


def calculate_sea_ice_risk(lat: float, lon: float, radius_km: float = 50.0) -> Dict:
    """
    Sea-ice risk using real NSIDC/sea-ice source data when available.
    Falls back to physics model only in demo mode.
    """
    sic = None
    source = "unavailable"
    data_mode = "live"

    # Try real source first
    try:
        from app.sources.sea_ice_source import get_sea_ice_source
        from app.core.live_gate import allow_demo_fallback
        src = get_sea_ice_source()
        latest = src.get_latest_extent()
        if latest:
            # Use real coverage as a proxy for local SIC
            # (NSIDC daily CSV gives overall coverage, not gridded local values)
            coverage_pct = latest.get("coverage_pct", 50.0) or 50.0
            # Scale to 0-1 and weight by latitude (more ice at higher latitudes)
            lat_factor = max(0, min(1, (abs(lat) - 55) / 25))
            sic = float(np.clip((coverage_pct / 100) * lat_factor * 1.2, 0, 1))
            source = latest.get("source", "NSIDC")
            data_mode = "live"
    except Exception:
        pass

    # Fall back to physics model
    if sic is None:
        from app.core.live_gate import allow_demo_fallback
        if allow_demo_fallback():
            from app.services.demo_service import _sic_at, _ice_category
            sic = _sic_at(lat, lon)
            source = "physics_model"
            data_mode = "demo"
        else:
            sic = 0.3  # conservative estimate
            source = "unavailable"

    from app.services.demo_service import _ice_category
    category = _ice_category(sic)
    risk = _sic_to_risk(sic)

    factors = []
    if sic > 0.80:
        factors.append(f"Consolidated ice ({sic*100:.0f}% SIC) — beset risk")
    elif sic > 0.60:
        factors.append(f"High sea-ice ({sic*100:.0f}% SIC) — reduced speed")
    elif sic > 0.40:
        factors.append(f"Moderate sea-ice ({sic*100:.0f}% SIC)")
    elif sic > 0.15:
        factors.append(f"Low sea-ice ({sic*100:.0f}% SIC) — minor hazard")
    else:
        factors.append("Open water — negligible ice risk")

    return {
        "score": float(np.clip(risk, 0, 1)),
        "sic": round(sic, 3),
        "category": category,
        "factors": factors,
        "source": source,
        "data_mode": data_mode,
    }


def calculate_iceberg_risk(lat: float, lon: float, radius_km: float = 100.0) -> Dict:
    """
    Iceberg risk using real NIC data when available.
    """
    # Try real icebergs first
    real_icebergs = []
    data_mode = "live"
    try:
        from app.sources.iceberg_source import get_iceberg_source
        real_icebergs = get_iceberg_source().get_icebergs()
    except Exception:
        pass

    if not real_icebergs:
        from app.core.live_gate import allow_demo_fallback
        if allow_demo_fallback():
            from app.services.demo_service import get_icebergs
            real_icebergs = get_icebergs().get("icebergs", [])
            data_mode = "demo"
        else:
            return {
                "score": 0.0, "nearby_count": 0, "closest_km": None,
                "factors": ["Iceberg data unavailable"], "data_mode": "offline"
            }

    from app.services.demo_service import haversine_km
    nearby = []
    for ib in real_icebergs:
        ib_lat = ib.get("latitude")
        ib_lon = ib.get("longitude")
        if ib_lat is None or ib_lon is None:
            continue
        dist = haversine_km(lat, lon, ib_lat, ib_lon)
        if dist <= radius_km:
            nearby.append({"iceberg": ib, "distance_km": dist})

    if not nearby:
        return {
            "score": 0.0, "nearby_count": 0, "closest_km": None,
            "factors": [f"No icebergs within {radius_km:.0f} km"],
            "data_mode": data_mode,
        }

    max_risk = 0.0
    factors = []
    closest_km = min(n["distance_km"] for n in nearby)

    for n in nearby:
        dist = n["distance_km"]
        ib = n["iceberg"]
        name = ib.get("iceberg_name", ib.get("name", "unknown"))
        area = ib.get("area_km2") or 100
        prox_risk = max(0, 1 - dist / radius_km)
        size_f = min(1.0, float(area) / 1000.0)
        traj_risk = 0.2 if ib.get("risk_level") == "high" else 0.1
        r = float(np.clip(prox_risk * 0.6 + size_f * 0.3 + traj_risk, 0, 1))
        if r > max_risk:
            max_risk = r
        if dist < 20:
            factors.append(f"Iceberg {name} is {dist:.1f} km — IMMEDIATE DANGER")
        elif dist < 50:
            factors.append(f"Iceberg {name} is {dist:.1f} km away")
        else:
            factors.append(f"Iceberg {name} at {dist:.0f} km — monitor")

    return {
        "score": float(np.clip(max_risk, 0, 1)),
        "nearby_count": len(nearby),
        "closest_km": round(closest_km, 1),
        "factors": factors[:5],
        "data_mode": data_mode,
    }


def calculate_weather_risk(lat: float, lon: float) -> Dict:
    """Weather risk using real Open-Meteo data when available."""
    wind_speed = None
    wave_h = None
    data_mode = "live"
    source = "Open-Meteo"

    try:
        from app.sources.weather_source import get_weather_source
        pt = get_weather_source().get_nearest(lat, lon)
        if pt:
            wind_speed = float(pt.get("wind_speed_ms") or 0)
            wave_h = 2.5  # Open-Meteo weather doesn't have wave height
            source = pt.get("source", "Open-Meteo")
    except Exception:
        pass

    # Try ocean source for wave height
    try:
        from app.sources.ocean_source import get_ocean_source
        pt = get_ocean_source().get_nearest(lat, lon)
        if pt:
            wave_h = float(pt.get("significant_wave_height_m") or wave_h or 2.5)
    except Exception:
        pass

    if wind_speed is None:
        from app.core.live_gate import allow_demo_fallback
        if allow_demo_fallback():
            seed = int(abs(lat * 100 + lon * 100)) % 99991
            rng = np.random.default_rng(seed)
            wind_speed = float(rng.uniform(5, 18))
            wave_h = float(rng.uniform(1.5, 5.0))
            data_mode = "demo"
            source = "physics_model"
        else:
            wind_speed, wave_h = 10.0, 2.5
            data_mode = "offline"
            source = "unavailable"

    wave_h = wave_h or 2.5
    wind_risk = (0.1 if wind_speed < 8 else 0.3 if wind_speed < 12
                 else 0.6 if wind_speed < 16 else 0.85)
    wave_risk = (0.1 if wave_h < 2.0 else 0.35 if wave_h < 3.5
                 else 0.65 if wave_h < 5.0 else 0.90)
    score = float(np.clip(0.6 * wind_risk + 0.4 * wave_risk, 0, 1))

    factors = [f"Wind: {wind_speed:.1f} m/s (source: {source})"]
    if wind_speed > 15:
        factors.append("Storm-force winds — dangerous conditions")
    elif wind_speed > 10:
        factors.append("Strong winds — reduced stability")
    factors.append(f"Wave height: ~{wave_h:.1f} m")

    return {
        "score": score,
        "wind_speed_ms": round(wind_speed, 2),
        "wave_height_m": round(wave_h, 2),
        "factors": factors,
        "source": source,
        "data_mode": data_mode,
    }


def calculate_ocean_risk(lat: float, lon: float) -> Dict:
    """Ocean current risk using real Open-Meteo Marine data."""
    current_speed = None
    sst = None
    data_mode = "live"
    source = "Open-Meteo Marine"

    try:
        from app.sources.ocean_source import get_ocean_source
        pt = get_ocean_source().get_nearest(lat, lon)
        if pt:
            current_speed = float(pt.get("current_speed_ms") or 0)
            sst = pt.get("sea_surface_temp_celsius")
            source = pt.get("source", "Open-Meteo Marine")
    except Exception:
        pass

    if current_speed is None:
        from app.core.live_gate import allow_demo_fallback
        if allow_demo_fallback():
            seed = int(abs(lat * 200 + lon * 200)) % 99991
            rng = np.random.default_rng(seed)
            u = float(rng.uniform(0.05, 0.45))
            v = float(rng.normal(0, 0.15))
            current_speed = math.sqrt(u**2 + v**2)
            sst = float(8 - 10 * (abs(lat) - 55) / 25 + rng.normal(0, 1))
            data_mode = "demo"
            source = "physics_model"
        else:
            current_speed, sst = 0.3, None
            data_mode = "offline"

    score = (0.1 if current_speed < 0.15 else 0.25 if current_speed < 0.30
             else 0.50 if current_speed < 0.45 else 0.75)

    factors = [f"Ocean current: {current_speed:.3f} m/s (source: {source})"]
    if current_speed > 0.4:
        factors.append("Strong ACC current — fuel penalty expected")
    if sst is not None and sst < -1.5:
        factors.append(f"Sub-freezing SST ({sst:.1f}°C) — icing risk")

    return {
        "score": float(np.clip(score, 0, 1)),
        "current_speed_ms": round(current_speed, 3),
        "sst_celsius": round(sst, 1) if sst is not None else None,
        "factors": factors,
        "source": source,
        "data_mode": data_mode,
    }


def calculate_risk(request: RiskCalculateRequest) -> Dict:
    """Multi-factor risk calculation using real data sources."""
    weights = request.weights or DEFAULT_WEIGHTS
    total_w = sum(weights.values())
    if abs(total_w - 1.0) > 0.01:
        weights = {k: v / total_w for k, v in weights.items()}

    ice_r    = calculate_sea_ice_risk(request.latitude, request.longitude, request.radius_km)
    iceberg_r = calculate_iceberg_risk(request.latitude, request.longitude, request.radius_km)
    weather_r = calculate_weather_risk(request.latitude, request.longitude)
    ocean_r   = calculate_ocean_risk(request.latitude, request.longitude)

    total = float(np.clip(
        weights.get("sea_ice", 0.35) * ice_r["score"] +
        weights.get("iceberg", 0.30) * iceberg_r["score"] +
        weights.get("weather", 0.20) * weather_r["score"] +
        weights.get("ocean", 0.15)   * ocean_r["score"],
        0, 1
    ))

    all_factors = []
    for r in [ice_r, iceberg_r, weather_r, ocean_r]:
        all_factors.extend([{"text": f, "source": r.get("source","calculated"),
                             "data_mode": r.get("data_mode","live")}
                            for f in r.get("factors", [])])

    recs = []
    if ice_r["score"] > 0.7:
        recs.append("Consolidated sea ice — avoid or reduce speed significantly")
    if iceberg_r["score"] > 0.6:
        recs.append("Iceberg risk — post lookouts, reduce speed, alter course")
    if weather_r["score"] > 0.6:
        recs.append("Storm conditions — consider shelter or delay")
    if ocean_r["score"] > 0.5:
        recs.append("Strong currents — increased fuel consumption")
    if not recs:
        recs.append("Conditions acceptable — standard polar navigation precautions apply")

    # Determine overall data quality
    modes = [ice_r.get("data_mode","live"), iceberg_r.get("data_mode","live"),
             weather_r.get("data_mode","live"), ocean_r.get("data_mode","live")]
    overall_mode = ("live" if all(m == "live" for m in modes)
                    else "partial" if any(m == "live" for m in modes)
                    else "demo")

    return {
        "latitude": request.latitude,
        "longitude": request.longitude,
        "radius_km": request.radius_km,
        "assessed_at": datetime.now(timezone.utc).isoformat(),
        "sea_ice_risk": round(ice_r["score"], 3),
        "iceberg_risk": round(iceberg_r["score"], 3),
        "weather_risk": round(weather_r["score"], 3),
        "ocean_risk": round(ocean_r["score"], 3),
        "total_risk_score": round(total, 3),
        "risk_category": _risk_category(total),
        "risk_factors": all_factors,
        "recommendations": recs,
        "data_mode": overall_mode,
        "component_sources": {
            "sea_ice": ice_r.get("source"),
            "iceberg": iceberg_r.get("data_mode"),
            "weather": weather_r.get("source"),
            "ocean": ocean_r.get("source"),
        },
    }
