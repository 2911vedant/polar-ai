"""
Iceberg service — uses real NIC data when available, demo fallback.
"""
from app.config import settings
from app.services import demo_service
from app.schemas.icebergs import TrajectoryPredictRequest
from app.core.freshness import FreshnessRegistry
from datetime import datetime, timezone
import math
import numpy as np


def _get_real_icebergs():
    """Return real NIC icebergs or empty list."""
    try:
        from app.sources.iceberg_source import get_iceberg_source
        real = get_iceberg_source().get_icebergs()
        if real:
            return real
    except Exception:
        pass
    return []


def _freshness_tag(is_real: bool) -> dict:
    f = FreshnessRegistry.get("icebergs")
    return {
        "freshness": f.to_dict() if f else None,
        "is_real": is_real,
        "data_mode": "live" if is_real else "demo",
    }


def list_icebergs():
    real = _get_real_icebergs()
    is_real = bool(real)

    if is_real:
        # Enrich real icebergs with computed risk and drift
        enriched = []
        for i, ib in enumerate(real):
            lat = ib.get("latitude", -65)
            lon = ib.get("longitude", -60)
            # Use demo drift model for trajectory hint
            drift_lat, drift_lon, speed, direction = demo_service._iceberg_drift(lat, lon, 24, i * 100)
            area = (ib.get("area_km2") or
                    ((ib.get("length_km") or 30) * (ib.get("width_km") or 10) * 0.85))
            # Risk based on size and proximity to typical shipping lanes
            risk = "high" if area > 1000 else ("medium" if area > 200 else "low")

            enriched.append({
                "id": f"nic-{ib['iceberg_name'].lower().replace(' ', '-')}",
                "iceberg_name": ib["iceberg_name"],
                "latitude": lat,
                "longitude": lon,
                "length_km": ib.get("length_km"),
                "width_km": ib.get("width_km"),
                "area_km2": round(area, 1),
                "drift_speed_kmh": round(speed, 3),
                "drift_direction_deg": round(direction, 1),
                "risk_level": risk,
                "status": "active",
                "last_observed_at": ib.get("last_observed_at"),
                "source": "US National Ice Center",
                "data_mode": "live",
            })

        result = {
            "icebergs": enriched,
            "total_count": len(enriched),
            "active_count": len(enriched),
            "high_risk_count": sum(1 for ib in enriched if ib["risk_level"] == "high"),
        }
        result.update(_freshness_tag(True))
        return result

    # Demo fallback
    result = demo_service.get_icebergs()
    result.update(_freshness_tag(False))
    return result


def get_iceberg_detail(iceberg_name: str):
    real = _get_real_icebergs()
    if real:
        ib = next((r for r in real if r.get("iceberg_name") == iceberg_name), None)
        if ib:
            lat, lon = ib["latitude"], ib["longitude"]
            # Build minimal detail from real data
            positions = []
            for h in range(0, 30 * 24, 12):  # 30 days, every 12h
                from datetime import timedelta
                t = datetime.now(timezone.utc) - timedelta(hours=h)
                pl, po, spd, dirn = demo_service._iceberg_drift(lat, lon, -h, hash(iceberg_name) % 9999)
                positions.append({
                    "observed_at": t.isoformat(),
                    "latitude": round(pl, 4), "longitude": round(po, 4),
                    "speed_kmh": spd, "direction_deg": dirn, "confidence": 0.9,
                })
            area = ib.get("area_km2") or (ib.get("length_km", 30) * ib.get("width_km", 10) * 0.85)
            return {
                "id": f"nic-{iceberg_name.lower().replace(' ', '-')}",
                "iceberg_name": iceberg_name,
                "latitude": lat, "longitude": lon,
                "length_km": ib.get("length_km"), "width_km": ib.get("width_km"),
                "area_km2": round(area, 1),
                "drift_speed_kmh": 0.3, "drift_direction_deg": 90,
                "risk_level": "high" if area > 1000 else "medium",
                "status": "active",
                "source": "US National Ice Center",
                "last_observed_at": ib.get("last_observed_at"),
                "positions": positions[-20:],
                "data_mode": "live",
                **_freshness_tag(True),
            }

    return demo_service.get_iceberg_detail(iceberg_name)


def get_trajectory(iceberg_name: str, horizon_hours: int = 72):
    result = demo_service.get_iceberg_trajectory(iceberg_name, horizon_hours)
    real = _get_real_icebergs()
    is_real = bool(real) and any(r.get("iceberg_name") == iceberg_name for r in real)
    if result:
        result.update(_freshness_tag(is_real))
    return result


def detect_icebergs():
    real = _get_real_icebergs()
    is_real = bool(real)
    icebergs_list = real if is_real else demo_service.get_icebergs()["icebergs"]
    return {
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "method": "nic_tracking" if is_real else "synthetic_detection_v1",
        "detections": [
            {
                "iceberg_name": ic.get("iceberg_name", ic.get("name", "?")),
                "latitude": ic.get("latitude", 0),
                "longitude": ic.get("longitude", 0),
                "estimated_area_km2": ic.get("area_km2"),
                "confidence": 1.0 if is_real else 0.87,
            }
            for ic in icebergs_list[:20]
        ],
        **_freshness_tag(is_real),
        "note": None if is_real else "DEMO DATA — Detection results are synthetic",
    }


def predict_trajectory(request: TrajectoryPredictRequest):
    return demo_service.get_iceberg_trajectory.__wrapped__(request) if hasattr(
        demo_service.get_iceberg_trajectory, "__wrapped__") else _predict_custom(request)


def _predict_custom(request: TrajectoryPredictRequest):
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    lat, lon = request.latitude, request.longitude
    trajectory = []
    for h in [1, 6, 12, 24, 48, 72]:
        if h <= request.horizon_hours:
            pl, po, spd, dirn = demo_service._iceberg_drift(lat, lon, h, hash(str(lat) + str(lon)) % 9999)
            trajectory.append({
                "horizon_hours": h,
                "valid_time": (now + timedelta(hours=h)).isoformat(),
                "latitude": round(pl, 4), "longitude": round(po, 4),
                "uncertainty_km": round(2.0 + h / 72.0 * 25.0, 1),
                "confidence": round(max(0.45, 1.0 - h / 168.0 * 0.6), 3),
            })
    return {
        "iceberg_id": "custom", "iceberg_name": request.iceberg_name or "Custom Point",
        "current_lat": lat, "current_lon": lon,
        "predicted_at": now.isoformat(), "trajectory": trajectory,
        "model_name": "physics_drift_v1",
        "closest_approach_km": None, "closest_approach_time": None,
        "data_mode": "demo",
    }
