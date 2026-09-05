"""
POLAR-AI Simulation Service
Manages the state of the interactive simulation for the SIH demo.
"""
import math
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from app.services import demo_service

# Simulation state (in-memory for demo)
_sim_state = {
    "running": False,
    "step": 0,
    "time_offset_hours": 0.0,
    "vessel_lat": -66.0,
    "vessel_lon": -60.0,
    "vessel_heading": 145.0,
    "vessel_speed_knots": 11.5,
    "current_route_type": "balanced",
    "route_recalculated": False,
    "recalculation_count": 0,
    "events": [],
    "icebergs_drift_factor": 0.0,
}

_SCENARIO_EVENTS = [
    (0,  "Route generated. Conditions nominal. Proceeding on balanced route."),
    (5,  "Ice condition update received. Sea-ice concentration increasing ahead."),
    (10, "Iceberg A-76A detected drifting toward vessel corridor."),
    (15, "Risk assessment updated. Overall risk: HIGH. Iceberg threat: ELEVATED."),
    (20, "WARNING: Iceberg A-76A trajectory intersects planned route at T+6h."),
    (22, "POLAR-AI initiating automatic route recalculation..."),
    (25, "New route computed. Deviation: +45 km. Risk reduced from HIGH to MODERATE."),
    (30, "New route accepted. Continuing on safer corridor. Iceberg A-76A clearing."),
    (40, "All systems nominal. Estimated arrival on schedule (+2h)."),
    (50, "Ice channel widening. Reverting to balanced route. Conditions improving."),
]


def get_state() -> Dict:
    """Get current simulation state."""
    step = _sim_state["step"]
    t = _sim_state["time_offset_hours"]

    # Drift icebergs based on simulation time
    icebergs = demo_service.get_icebergs()["icebergs"]
    sim_icebergs = []
    for i, ib in enumerate(icebergs):
        drift_lat, drift_lon, spd, dirn = demo_service._iceberg_drift(
            ib["latitude"], ib["longitude"],
            t_hours=t, rng_seed=i * 100
        )
        sim_ib = {**ib, "latitude": round(drift_lat, 4), "longitude": round(drift_lon, 4)}
        sim_icebergs.append(sim_ib)

    # Vessel movement along a simple bearing
    vessel_lat = _sim_state["vessel_lat"] + (step * 0.02)
    vessel_lon = _sim_state["vessel_lon"] + (step * 0.03)
    vessel_lat = float(np.clip(vessel_lat, -80, -55))

    # Current events (up to this step)
    events = [
        {"step": ev[0], "message": ev[1], "is_alert": "WARNING" in ev[1] or "POLAR-AI" in ev[1]}
        for ev in _SCENARIO_EVENTS
        if ev[0] <= step
    ]

    # Route changes
    route_status = "original"
    if step >= 22 and step < 25:
        route_status = "recalculating"
    elif step >= 25:
        route_status = "replanned"

    return {
        "running": _sim_state["running"],
        "step": step,
        "time_offset_hours": round(t, 2),
        "vessel": {
            "latitude": round(vessel_lat, 4),
            "longitude": round(vessel_lon, 4),
            "heading_deg": _sim_state["vessel_heading"],
            "speed_knots": _sim_state["vessel_speed_knots"],
        },
        "icebergs": sim_icebergs,
        "route_status": route_status,
        "risk_score": _compute_sim_risk(step),
        "risk_category": _compute_sim_risk_cat(step),
        "events": events,
        "scenario_complete": step >= 50,
        "data_mode": "demo",
    }


def _compute_sim_risk(step: int) -> float:
    """Risk increases during iceberg approach, decreases after reroute."""
    if step < 10:
        return 0.35
    elif step < 20:
        return 0.35 + (step - 10) * 0.04
    elif step < 25:
        return 0.75
    elif step < 30:
        return 0.75 - (step - 25) * 0.06
    else:
        return 0.45


def _compute_sim_risk_cat(step: int) -> str:
    r = _compute_sim_risk(step)
    if r < 0.25: return "low"
    elif r < 0.50: return "moderate"
    elif r < 0.75: return "high"
    else: return "extreme"


def start() -> Dict:
    _sim_state["running"] = True
    return {"status": "started", **get_state()}


def pause() -> Dict:
    _sim_state["running"] = False
    return {"status": "paused", **get_state()}


def reset() -> Dict:
    _sim_state["running"] = False
    _sim_state["step"] = 0
    _sim_state["time_offset_hours"] = 0.0
    _sim_state["vessel_lat"] = -66.0
    _sim_state["vessel_lon"] = -60.0
    _sim_state["route_recalculated"] = False
    _sim_state["recalculation_count"] = 0
    _sim_state["events"] = []
    return {"status": "reset", **get_state()}


def step() -> Dict:
    """Advance simulation by one step."""
    _sim_state["step"] = min(_sim_state["step"] + 1, 60)
    _sim_state["time_offset_hours"] += 0.5  # 30 min per step

    if _sim_state["step"] == 22:
        _sim_state["route_recalculated"] = False
    elif _sim_state["step"] == 25:
        _sim_state["route_recalculated"] = True
        _sim_state["recalculation_count"] += 1

    return {"status": "stepped", **get_state()}
