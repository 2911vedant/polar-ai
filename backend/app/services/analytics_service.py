"""Analytics service — generates trend data and model performance metrics."""
import math
import numpy as np
from datetime import datetime, timezone, timedelta
from app.services import demo_service


def get_analytics(days: int = 30):
    now = datetime.now(timezone.utc)

    # Sea ice trend
    ice_trend = []
    for d in range(days, -1, -1):
        ts = now - timedelta(days=d)
        doy = ts.timetuple().tm_yday
        seasonal = 0.5 + 0.5 * math.cos(2 * math.pi * (doy - 210) / 365)
        coverage = 45 + 20 * seasonal
        rng = np.random.default_rng(doy + 500)
        coverage += float(rng.normal(0, 1.5))
        ice_trend.append({
            "date": ts.strftime("%Y-%m-%d"),
            "coverage_pct": round(float(np.clip(coverage, 25, 70)), 1),
        })

    # Iceberg count over time
    iceberg_trend = []
    base_count = 12
    for d in range(days, -1, -1):
        ts = now - timedelta(days=d)
        rng = np.random.default_rng(d + 200)
        count = base_count + int(rng.integers(-2, 3))
        iceberg_trend.append({
            "date": ts.strftime("%Y-%m-%d"),
            "count": max(0, count),
        })

    # Route risk over time
    route_risk_trend = []
    for d in range(days, -1, -1):
        ts = now - timedelta(days=d)
        rng = np.random.default_rng(d + 300)
        risk = float(rng.uniform(0.3, 0.7))
        route_risk_trend.append({
            "date": ts.strftime("%Y-%m-%d"),
            "risk_score": round(risk, 3),
        })

    # Forecast accuracy
    forecast_accuracy = [
        {"horizon": "24h", "mae": 0.042, "rmse": 0.061, "skill_score": 0.78, "n_samples": 90},
        {"horizon": "48h", "mae": 0.068, "rmse": 0.094, "skill_score": 0.65, "n_samples": 90},
        {"horizon": "72h", "mae": 0.091, "rmse": 0.124, "skill_score": 0.54, "n_samples": 90},
        {"horizon": "7d",  "mae": 0.143, "rmse": 0.187, "skill_score": 0.38, "n_samples": 45},
    ]

    # Weather distribution
    weather_dist = []
    conditions = ["Clear", "Partly Cloudy", "Overcast", "Fog", "Snow", "Storm"]
    weights_w = [0.15, 0.20, 0.30, 0.10, 0.18, 0.07]
    for cond, pct in zip(conditions, weights_w):
        weather_dist.append({"condition": cond, "frequency_pct": round(pct * 100, 1)})

    # Fuel efficiency by route type
    fuel_efficiency = [
        {"route_type": "Shortest",       "avg_fuel_index": 1.00, "avg_distance_km": 820},
        {"route_type": "Safest",         "avg_fuel_index": 1.12, "avg_distance_km": 940},
        {"route_type": "Fuel Efficient", "avg_fuel_index": 0.94, "avg_distance_km": 870},
        {"route_type": "Balanced",       "avg_fuel_index": 1.05, "avg_distance_km": 890},
    ]

    return {
        "period_days": days,
        "generated_at": now.isoformat(),
        "sea_ice_trend": ice_trend,
        "iceberg_count_trend": iceberg_trend,
        "route_risk_trend": route_risk_trend,
        "forecast_accuracy": forecast_accuracy,
        "weather_distribution": weather_dist,
        "fuel_efficiency_by_route": fuel_efficiency,
        "summary": {
            "avg_sea_ice_coverage": round(float(np.mean([p["coverage_pct"] for p in ice_trend])), 1),
            "avg_iceberg_count": round(float(np.mean([p["count"] for p in iceberg_trend])), 1),
            "avg_route_risk": round(float(np.mean([p["risk_score"] for p in route_risk_trend])), 3),
            "best_model_horizon": "24h",
            "best_skill_score": 0.78,
        },
        "data_mode": "demo",
    }
