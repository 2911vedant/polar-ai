"""
POLAR-AI Demo Data Service
Generates deterministic synthetic Antarctic data using fixed random seed.
All output is clearly labeled as DEMO/SIMULATION data.

This is the backbone of the demo mode - all other services call this
when DATA_MODE=demo or when real data is unavailable.
"""
import numpy as np
import math
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from functools import lru_cache
from app.config import settings

# Fixed seed for full reproducibility
RNG = np.random.default_rng(settings.DEMO_RANDOM_SEED)

# Antarctic geographic bounds
ANT_LAT_MIN = -80.0
ANT_LAT_MAX = -55.0
ANT_LON_MIN = -180.0
ANT_LON_MAX = 180.0

# Demo grid resolution
GRID_LAT_STEPS = 25   # 25 rows
GRID_LON_STEPS = 36   # 36 columns (every 10°)

# Named research stations as navigation waypoints
STATIONS = {
    "McMurdo": (-77.85, 166.67),
    "Palmer": (-64.77, -64.05),
    "Rothera": (-67.57, -68.13),
    "Mawson": (-67.60, 62.87),
    "Casey": (-66.28, 110.52),
    "Davis": (-68.58, 77.97),
    "Halley": (-75.52, -26.57),
    "Neumayer": (-70.68, -8.26),
    "Concordia": (-75.10, 123.35),
    "Amundsen-Scott": (-90.0, 0.0),
}

# ── Sea Ice ───────────────────────────────────────────────────────────────────


def _sic_at(lat: float, lon: float, t_offset_days: float = 0) -> float:
    """
    Physics-inspired sea-ice concentration model.
    - Higher concentration near the pole and at high latitudes
    - Seasonal variation (max in austral winter ~September, min ~February)
    - Longitudinal variation (Ross Sea / Weddell Sea asymmetry)
    """
    # Base concentration increases toward pole
    lat_factor = (abs(lat) - 55.0) / 25.0  # 0 at -55°, 1 at -80°
    lat_factor = np.clip(lat_factor, 0, 1)

    # Seasonal cycle (day of year, assuming Jan 1 = day 0)
    doy = (datetime.now(timezone.utc).timetuple().tm_yday + t_offset_days) % 365
    # Austral winter = days ~180-270 (max ice)
    seasonal = 0.5 + 0.5 * math.cos(2 * math.pi * (doy - 210) / 365)

    # Longitudinal asymmetry (Weddell Sea cold, West Pacific warm)
    lon_rad = math.radians(lon)
    lon_factor = 0.1 * math.sin(lon_rad + 0.5)

    sic = lat_factor * (0.6 + 0.3 * seasonal) + lon_factor
    # Add deterministic spatial noise
    noise_seed = int(abs(lat * 100) + abs(lon * 100)) % 1000
    noise = np.random.default_rng(noise_seed).normal(0, 0.05)
    sic = np.clip(sic + noise, 0.0, 1.0)
    return float(sic)


def _ice_category(sic: float) -> str:
    if sic < 0.15:
        return "open_water"
    elif sic < 0.40:
        return "low"
    elif sic < 0.65:
        return "moderate"
    elif sic < 0.85:
        return "high"
    else:
        return "consolidated"


@lru_cache(maxsize=4)
def get_sea_ice_grid(resolution: str = "low", t_offset_days: float = 0):
    """Generate sea-ice concentration grid for Antarctica."""
    if resolution == "low":
        lat_steps, lon_steps = 20, 24
    elif resolution == "medium":
        lat_steps, lon_steps = 30, 36
    else:
        lat_steps, lon_steps = 50, 72

    lats = np.linspace(ANT_LAT_MIN, ANT_LAT_MAX, lat_steps)
    lons = np.linspace(ANT_LON_MIN, ANT_LON_MAX, lon_steps)

    grid_points = []
    total_cells = 0
    covered_cells = 0

    for i, lat in enumerate(lats):
        for j, lon in enumerate(lons):
            sic = _sic_at(lat, lon, t_offset_days)
            category = _ice_category(sic)
            total_cells += 1
            if sic > 0.15:
                covered_cells += 1
            grid_points.append({
                "latitude": round(float(lat), 2),
                "longitude": round(float(lon), 2),
                "concentration": round(sic, 3),
                "ice_category": category,
                "grid_x": j,
                "grid_y": i,
            })

    coverage_pct = (covered_cells / total_cells) * 100 if total_cells > 0 else 0
    # Antarctic sea ice extent ~ 10-15 million km²
    extent_km2 = coverage_pct / 100 * 20_000_000

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "grid_points": grid_points,
        "coverage_pct": round(coverage_pct, 1),
        "extent_km2": round(extent_km2, 0),
        "source": "synthetic_model_v1",
        "data_mode": "demo",
    }


def get_sea_ice_history(days: int = 90):
    """Generate synthetic sea-ice coverage history."""
    now = datetime.now(timezone.utc)
    data_points = []
    for d in range(days, -1, -1):
        ts = now - timedelta(days=d)
        doy = ts.timetuple().tm_yday
        # Coverage varies seasonally: 30-65% of Antarctic circle
        seasonal = 0.5 + 0.5 * math.cos(2 * math.pi * (doy - 210) / 365)
        coverage = 45 + 20 * seasonal
        noise_rng = np.random.default_rng(doy + 1000)
        coverage += noise_rng.normal(0, 1.5)
        coverage = float(np.clip(coverage, 25, 70))
        extent_km2 = coverage / 100 * 20_000_000
        # Anomaly: difference from 30-year mean
        mean_coverage = 48.0
        anomaly = coverage - mean_coverage
        data_points.append({
            "date": ts.isoformat(),
            "coverage_pct": round(coverage, 2),
            "extent_km2": round(extent_km2, 0),
            "anomaly_pct": round(anomaly, 2),
        })
    return {
        "start_date": (now - timedelta(days=days)).isoformat(),
        "end_date": now.isoformat(),
        "data_points": data_points,
        "source": "synthetic_history",
        "data_mode": "demo",
    }


def get_sea_ice_forecast(horizon_hours: int = 72):
    """Generate sea-ice forecast for next N hours."""
    now = datetime.now(timezone.utc)
    horizons = [24, 48, 72] if horizon_hours >= 72 else [24, 48]
    if horizon_hours not in horizons:
        horizons = sorted(set(horizons + [horizon_hours]))

    lat_steps, lon_steps = 15, 18
    lats = np.linspace(-80, -60, lat_steps)
    lons = np.linspace(-180, 180, lon_steps)

    result = []
    for h in horizons:
        t_offset = h / 24.0
        grid_points = []
        for lat in lats:
            for lon in lons:
                base_sic = _sic_at(lat, lon, t_offset)
                # Uncertainty grows with horizon
                uncertainty = 0.03 + (h / 168.0) * 0.12
                confidence = max(0.5, 1.0 - (h / 168.0) * 0.5)
                risk_cat = _ice_category(base_sic)
                grid_points.append({
                    "latitude": round(float(lat), 2),
                    "longitude": round(float(lon), 2),
                    "predicted_concentration": round(float(base_sic), 3),
                    "uncertainty": round(uncertainty, 3),
                    "confidence": round(float(confidence), 3),
                    "risk_category": risk_cat,
                })
        result.append({
            "generated_at": now.isoformat(),
            "valid_time": (now + timedelta(hours=h)).isoformat(),
            "horizon_hours": h,
            "grid_points": grid_points,
            "model_name": "rf_baseline_v1",
            "overall_confidence": round(max(0.5, 1.0 - (h / 168.0) * 0.5), 3),
            "mae": round(0.04 + (h / 168.0) * 0.08, 4),
            "rmse": round(0.06 + (h / 168.0) * 0.10, 4),
            "data_mode": "demo",
        })
    return result


# ── Icebergs ──────────────────────────────────────────────────────────────────

# Predefined demo icebergs with realistic Antarctic positions
DEMO_ICEBERGS = [
    {"name": "A-76A", "lat": -67.2, "lon": -51.8, "length": 135, "width": 26, "area": 2800, "risk": "high"},
    {"name": "A-76B", "lat": -68.9, "lon": -53.2, "length": 89, "width": 18, "area": 1240, "risk": "medium"},
    {"name": "A-76C", "lat": -66.4, "lon": -50.1, "length": 42, "width": 12, "area": 380, "risk": "medium"},
    {"name": "B-22A", "lat": -72.1, "lon": -102.3, "length": 58, "width": 14, "area": 620, "risk": "medium"},
    {"name": "C-38", "lat": -64.8, "lon": 148.7, "length": 31, "width": 9,  "area": 210, "risk": "low"},
    {"name": "D-15A", "lat": -66.1, "lon": 95.4, "length": 77, "width": 22, "area": 890, "risk": "medium"},
    {"name": "D-20", "lat": -69.3, "lon": 92.1, "length": 22, "width": 7,  "area": 115, "risk": "low"},
    {"name": "A-83", "lat": -74.5, "lon": -60.1, "length": 105, "width": 31, "area": 2100, "risk": "high"},
    {"name": "B-31", "lat": -71.8, "lon": -97.5, "length": 48, "width": 15, "area": 520, "risk": "medium"},
    {"name": "C-44", "lat": -62.3, "lon": 143.2, "length": 19, "width": 6,  "area": 87, "risk": "low"},
    {"name": "A-68A", "lat": -55.1, "lon": -38.2, "length": 25, "width": 8,  "area": 145, "risk": "high"},  # near shipping lanes
    {"name": "B-46",  "lat": -75.2, "lon": -107.4, "length": 34, "width": 11, "area": 280, "risk": "low"},
]


def _iceberg_drift(lat: float, lon: float, t_hours: float, rng_seed: int):
    """
    Physics-inspired iceberg drift model.
    Icebergs drift primarily due to:
    1. Ocean currents (Antarctic Circumpolar Current: ~westward at high lat)
    2. Wind drag (10% of wind speed)
    3. Coriolis effect (deflects left in Southern Hemisphere)
    """
    local_rng = np.random.default_rng(rng_seed)
    # ACC base current: eastward at 0.3-0.5 km/h
    acc_speed = 0.3 + local_rng.uniform(0, 0.2)
    # Wind contribution: random but persistent
    wind_u = local_rng.normal(0.05, 0.15)
    wind_v = local_rng.normal(-0.02, 0.10)

    total_u_kmh = acc_speed * math.cos(math.radians(lon)) + wind_u
    total_v_kmh = acc_speed * math.sin(math.radians(lat)) + wind_v

    # Coriolis (Southern Hemisphere: deflect left)
    coriolis_factor = 0.1 * math.sin(math.radians(abs(lat)))
    total_u_kmh += coriolis_factor * total_v_kmh
    total_v_kmh -= coriolis_factor * total_u_kmh

    delta_lat = (total_v_kmh * t_hours) / 111.0
    delta_lon = (total_u_kmh * t_hours) / (111.0 * math.cos(math.radians(lat)))

    new_lat = float(np.clip(lat + delta_lat, -80, -55))
    new_lon = float(lon + delta_lon)
    if new_lon > 180:
        new_lon -= 360
    if new_lon < -180:
        new_lon += 360

    speed = math.sqrt(total_u_kmh ** 2 + total_v_kmh ** 2)
    direction = math.degrees(math.atan2(total_u_kmh, total_v_kmh)) % 360

    return new_lat, new_lon, round(speed, 3), round(direction, 1)


def get_icebergs():
    """Return list of all demo icebergs with current positions."""
    now = datetime.now(timezone.utc)
    icebergs = []
    for i, iceberg in enumerate(DEMO_ICEBERGS):
        lat, lon, speed, direction = _iceberg_drift(
            iceberg["lat"], iceberg["lon"],
            t_hours=0, rng_seed=i * 100
        )
        area = iceberg["length"] * iceberg["width"] * 0.85
        icebergs.append({
            "id": f"iceberg-{iceberg['name'].lower().replace('-', '')}",
            "iceberg_name": iceberg["name"],
            "latitude": round(lat, 4),
            "longitude": round(lon, 4),
            "length_km": float(iceberg["length"]),
            "width_km": float(iceberg["width"]),
            "area_km2": round(area, 1),
            "drift_speed_kmh": speed,
            "drift_direction_deg": direction,
            "risk_level": iceberg["risk"],
            "status": "active",
            "last_observed_at": (now - timedelta(hours=6)).isoformat(),
            "data_mode": "demo",
        })
    return {
        "icebergs": icebergs,
        "total_count": len(icebergs),
        "active_count": len(icebergs),
        "high_risk_count": sum(1 for ic in icebergs if ic["risk_level"] == "high"),
        "data_mode": "demo",
    }


def get_iceberg_detail(iceberg_name: str) -> Optional[Dict]:
    """Return full detail for a named iceberg including position history."""
    now = datetime.now(timezone.utc)
    # Find in demo list
    demo = next((ic for ic in DEMO_ICEBERGS if ic["name"] == iceberg_name), None)
    if not demo:
        return None

    idx = DEMO_ICEBERGS.index(demo)

    # Build position history (last 30 days, every 12 hours)
    positions = []
    for h_back in range(720, -1, -12):  # 720h = 30 days
        past_lat, past_lon, speed, direction = _iceberg_drift(
            demo["lat"], demo["lon"],
            t_hours=-h_back, rng_seed=idx * 100 + h_back
        )
        positions.append({
            "observed_at": (now - timedelta(hours=h_back)).isoformat(),
            "latitude": round(past_lat, 4),
            "longitude": round(past_lon, 4),
            "speed_kmh": speed,
            "direction_deg": direction,
            "confidence": 0.95 if h_back < 48 else 0.85,
        })

    lat, lon, speed, direction = _iceberg_drift(demo["lat"], demo["lon"], 0, idx * 100)
    area = demo["length"] * demo["width"] * 0.85

    return {
        "id": f"iceberg-{demo['name'].lower().replace('-', '')}",
        "iceberg_name": demo["name"],
        "latitude": round(lat, 4),
        "longitude": round(lon, 4),
        "length_km": float(demo["length"]),
        "width_km": float(demo["width"]),
        "area_km2": round(area, 1),
        "drift_speed_kmh": speed,
        "drift_direction_deg": direction,
        "risk_level": demo["risk"],
        "status": "active",
        "source": "demo",
        "last_observed_at": (now - timedelta(hours=6)).isoformat(),
        "positions": positions[-20:],  # last 20 positions
        "data_mode": "demo",
    }


def get_iceberg_trajectory(iceberg_name: str, horizon_hours: int = 72):
    """Predict iceberg trajectory using physics drift model."""
    now = datetime.now(timezone.utc)
    demo = next((ic for ic in DEMO_ICEBERGS if ic["name"] == iceberg_name), None)
    if not demo:
        return None

    idx = DEMO_ICEBERGS.index(demo)
    lat, lon, speed, direction = _iceberg_drift(demo["lat"], demo["lon"], 0, idx * 100)

    horizons = [1, 6, 12, 24, 48, 72]
    if horizon_hours > 72:
        horizons.append(horizon_hours)

    trajectory = []
    for h in [hh for hh in horizons if hh <= horizon_hours]:
        pred_lat, pred_lon, pred_speed, pred_dir = _iceberg_drift(
            lat, lon, h, rng_seed=idx * 100 + h
        )
        uncertainty_km = 2.0 + (h / 72.0) * 30.0
        confidence = max(0.4, 1.0 - (h / 168.0) * 0.6)
        trajectory.append({
            "horizon_hours": h,
            "valid_time": (now + timedelta(hours=h)).isoformat(),
            "latitude": round(pred_lat, 4),
            "longitude": round(pred_lon, 4),
            "uncertainty_km": round(uncertainty_km, 1),
            "confidence": round(float(confidence), 3),
        })

    # Vessel position for closest approach calculation
    vessel_lat, vessel_lon = -66.0, -60.0  # demo vessel position
    closest_approach_km = None
    closest_approach_time = None
    min_dist = float("inf")
    for tp in trajectory:
        dist = _haversine_km(tp["latitude"], tp["longitude"], vessel_lat, vessel_lon)
        if dist < min_dist:
            min_dist = dist
            closest_approach_km = round(dist, 1)
            closest_approach_time = tp["valid_time"]

    return {
        "iceberg_id": f"iceberg-{demo['name'].lower().replace('-', '')}",
        "iceberg_name": demo["name"],
        "current_lat": round(lat, 4),
        "current_lon": round(lon, 4),
        "predicted_at": now.isoformat(),
        "trajectory": trajectory,
        "model_name": "physics_drift_v1",
        "closest_approach_km": closest_approach_km,
        "closest_approach_time": closest_approach_time,
        "data_mode": "demo",
    }


# ── Weather ───────────────────────────────────────────────────────────────────

def get_weather(t_offset_hours: float = 0):
    """Generate weather grid for Antarctic region."""
    now = datetime.now(timezone.utc)
    lat_steps, lon_steps = 12, 18
    lats = np.linspace(-80, -58, lat_steps)
    lons = np.linspace(-180, 180, lon_steps)

    grid_points = []
    total_wind = 0.0
    min_temp = 100.0

    for i, lat in enumerate(lats):
        for j, lon in enumerate(lons):
            seed = int(abs(lat * 100 + lon * 100 + t_offset_hours)) % 99991
            rng = np.random.default_rng(seed)

            # Wind: 20-60 km/h in Southern Ocean (5-17 m/s)
            wind_speed = float(rng.uniform(5, 18))
            wind_dir = float(rng.uniform(0, 360))

            # Temperature: -25°C to -5°C near coast, colder inland
            lat_factor = (abs(lat) - 55) / 25
            temp = float(-5 - 20 * lat_factor + rng.normal(0, 3))
            temp += math.sin(2 * math.pi * t_offset_hours / 24) * 2  # diurnal

            pressure = float(rng.uniform(960, 1010))
            precip = float(max(0, rng.normal(0.5, 0.8)))

            # Wind risk: >15 m/s is high risk
            wind_risk = float(np.clip((wind_speed - 5) / 15, 0, 1))

            total_wind += wind_speed
            if temp < min_temp:
                min_temp = temp

            grid_points.append({
                "latitude": round(float(lat), 2),
                "longitude": round(float(lon), 2),
                "wind_speed_ms": round(wind_speed, 2),
                "wind_direction_deg": round(wind_dir, 1),
                "air_temp_celsius": round(temp, 1),
                "sea_level_pressure_hpa": round(pressure, 1),
                "precipitation_mm": round(precip, 2),
                "weather_risk_score": round(wind_risk, 3),
                "source": "demo",
            })

    avg_wind = total_wind / len(grid_points)
    return {
        "timestamp": (now + timedelta(hours=t_offset_hours)).isoformat(),
        "grid_points": grid_points,
        "avg_wind_speed_ms": round(avg_wind, 2),
        "min_temp_celsius": round(min_temp, 1),
        "data_mode": "demo",
    }


def get_weather_forecast(horizon_hours: int = 72):
    """Generate weather forecast."""
    forecasts = []
    for h in [6, 12, 24, 48, 72]:
        if h <= horizon_hours:
            weather = get_weather(t_offset_hours=h)
            forecasts.append({
                "horizon_hours": h,
                **weather,
            })
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "forecasts": forecasts,
        "data_mode": "demo",
    }


# ── Ocean ─────────────────────────────────────────────────────────────────────

def get_ocean():
    """Generate ocean conditions for Antarctic region."""
    now = datetime.now(timezone.utc)
    lat_steps, lon_steps = 12, 18
    lats = np.linspace(-80, -58, lat_steps)
    lons = np.linspace(-180, 180, lon_steps)

    grid_points = []
    total_speed = 0.0
    total_sst = 0.0

    for i, lat in enumerate(lats):
        for j, lon in enumerate(lons):
            seed = int(abs(lat * 200 + lon * 200)) % 99991
            rng = np.random.default_rng(seed)

            # Antarctic Circumpolar Current: eastward 0.1-0.5 m/s
            u = float(rng.uniform(0.05, 0.4))
            v = float(rng.normal(0, 0.1))
            speed = math.sqrt(u**2 + v**2)
            direction = math.degrees(math.atan2(u, v)) % 360

            # SST: -2°C to +6°C (colder near sea ice)
            lat_factor = (abs(lat) - 55) / 25
            sst = float(8 - 10 * lat_factor + rng.normal(0, 1))

            # Wave height: 2-5m in Southern Ocean
            wave_h = float(rng.uniform(1.5, 5.0))
            wave_period = float(rng.uniform(8, 15))

            # Ocean risk: high speed or rough waves
            ocean_risk = float(np.clip(speed / 0.5 * 0.3 + (wave_h - 1.5) / 3.5 * 0.7, 0, 1))

            total_speed += speed
            total_sst += sst

            grid_points.append({
                "latitude": round(float(lat), 2),
                "longitude": round(float(lon), 2),
                "current_speed_ms": round(speed, 3),
                "current_direction_deg": round(direction, 1),
                "current_u_ms": round(u, 3),
                "current_v_ms": round(v, 3),
                "sea_surface_temp_celsius": round(sst, 1),
                "significant_wave_height_m": round(wave_h, 2),
                "ocean_risk_score": round(ocean_risk, 3),
                "source": "demo",
            })

    n = len(grid_points)
    return {
        "timestamp": now.isoformat(),
        "grid_points": grid_points,
        "avg_current_speed_ms": round(total_speed / n, 3),
        "avg_sst_celsius": round(total_sst / n, 1),
        "data_mode": "demo",
    }


# ── Dashboard ─────────────────────────────────────────────────────────────────

def get_dashboard_stats():
    """Return aggregated dashboard statistics."""
    now = datetime.now(timezone.utc)

    ice_grid = get_sea_ice_grid("low")
    icebergs = get_icebergs()
    weather = get_weather()
    ocean = get_ocean()

    # Compute overall risk
    avg_sic = float(np.mean([gp["concentration"] for gp in ice_grid["grid_points"]]))
    avg_wind = weather["avg_wind_speed_ms"]
    avg_current = ocean["avg_current_speed_ms"]
    high_risk_icebergs = icebergs["high_risk_count"]

    ice_risk = float(np.clip(avg_sic * 1.5, 0, 1))
    wind_risk = float(np.clip((avg_wind - 5) / 15, 0, 1))
    ocean_risk = float(np.clip(avg_current / 0.5, 0, 1))
    iceberg_risk = float(np.clip(high_risk_icebergs / 5, 0, 1))

    total_risk = 0.35 * ice_risk + 0.30 * iceberg_risk + 0.20 * wind_risk + 0.15 * ocean_risk
    total_risk = float(np.clip(total_risk, 0, 1))

    if total_risk < 0.25:
        risk_cat = "low"
    elif total_risk < 0.50:
        risk_cat = "moderate"
    elif total_risk < 0.75:
        risk_cat = "high"
    else:
        risk_cat = "extreme"

    # Simulated forecast accuracy metrics
    forecast_accuracy = [
        {"horizon": "24h", "mae": 0.042, "rmse": 0.061, "skill_score": 0.78},
        {"horizon": "48h", "mae": 0.068, "rmse": 0.094, "skill_score": 0.65},
        {"horizon": "72h", "mae": 0.091, "rmse": 0.124, "skill_score": 0.54},
        {"horizon": "7d",  "mae": 0.143, "rmse": 0.187, "skill_score": 0.38},
    ]

    return {
        "sea_ice_coverage_pct": ice_grid["coverage_pct"],
        "sea_ice_extent_km2": ice_grid["extent_km2"],
        "active_icebergs": icebergs["active_count"],
        "high_risk_icebergs": icebergs["high_risk_count"],
        "current_risk_score": round(total_risk * 100, 1),
        "current_risk_category": risk_cat,
        "sea_ice_risk": round(ice_risk * 100, 1),
        "iceberg_risk": round(iceberg_risk * 100, 1),
        "weather_risk": round(wind_risk * 100, 1),
        "ocean_risk": round(ocean_risk * 100, 1),
        "avg_wind_speed_ms": avg_wind,
        "avg_sst_celsius": ocean["avg_sst_celsius"],
        "vessel_status": "underway",
        "vessel_lat": -66.0,
        "vessel_lon": -60.0,
        "vessel_speed_knots": 11.5,
        "vessel_heading_deg": 145.0,
        "forecast_accuracy": forecast_accuracy,
        "data_mode": "demo",
        "disclaimer": "SIMULATION DATA — Not for real navigation",
        "last_updated": now.isoformat(),
    }


# ── Utilities ─────────────────────────────────────────────────────────────────

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance in km."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return _haversine_km(lat1, lon1, lat2, lon2)
