"""
POLAR-AI Route Planning Service
Implements A* navigation routing with multi-objective cost functions.

Route types:
  shortest       — minimize distance
  safest         — minimize risk (ice + iceberg + weather + ocean)
  fuel_efficient — minimize fuel (distance + current headwind penalty)
  balanced       — weighted combination of all factors
"""
import math
import heapq
import uuid
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
from app.services import demo_service, risk_service

# Grid resolution for A* (degrees)
GRID_STEP = 1.0  # 1° ≈ 111 km

# Route type cost weight configurations
ROUTE_WEIGHTS = {
    "shortest": {
        "distance": 0.90, "fuel": 0.05, "risk": 0.04, "sea_ice": 0.005, "iceberg": 0.005,
    },
    "safest": {
        "distance": 0.10, "fuel": 0.05, "risk": 0.50, "sea_ice": 0.20, "iceberg": 0.15,
    },
    "fuel_efficient": {
        "distance": 0.40, "fuel": 0.45, "risk": 0.10, "sea_ice": 0.03, "iceberg": 0.02,
    },
    "balanced": {
        "distance": 0.30, "fuel": 0.25, "risk": 0.25, "sea_ice": 0.10, "iceberg": 0.10,
    },
}

# In-memory route cache for GET /routes/{id}
_route_cache: Dict[str, Dict] = {}


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _node_cost(lat: float, lon: float, weights: Dict[str, float]) -> float:
    """Compute traversal cost for a grid cell."""
    sic = demo_service._sic_at(lat, lon)

    # Iceberg proximity cost
    icebergs = demo_service.get_icebergs()["icebergs"]
    min_iceberg_dist = 9999.0
    for ib in icebergs:
        d = _haversine_km(lat, lon, ib["latitude"], ib["longitude"])
        if d < min_iceberg_dist:
            min_iceberg_dist = d
    iceberg_cost = float(np.clip(1.0 - min_iceberg_dist / 150.0, 0, 1))

    # Weather cost (wind at this cell)
    seed = int(abs(lat * 100 + lon * 100)) % 99991
    rng = np.random.default_rng(seed)
    wind_speed = float(rng.uniform(5, 18))
    weather_cost = float(np.clip((wind_speed - 5) / 15, 0, 1))

    # Ocean current (head/tailwind cost)
    ocean_rng = np.random.default_rng(int(abs(lat * 200 + lon * 200)) % 99991)
    current_u = float(ocean_rng.uniform(0.05, 0.45))
    ocean_cost = float(np.clip(current_u / 0.5, 0, 1))

    # Ice passability
    if sic > 0.90:
        return 999.0  # impassable
    elif sic > 0.70:
        ice_cost = 0.8
    elif sic > 0.40:
        ice_cost = 0.4 + (sic - 0.40) / 0.30 * 0.4
    elif sic > 0.15:
        ice_cost = (sic - 0.15) / 0.25 * 0.4
    else:
        ice_cost = 0.0

    cost = (
        weights.get("sea_ice", 0.3) * ice_cost +
        weights.get("iceberg", 0.2) * iceberg_cost +
        weights.get("risk", 0.3) * (ice_cost * 0.5 + iceberg_cost * 0.3 + weather_cost * 0.2) +
        weights.get("fuel", 0.1) * ocean_cost
    )
    return float(np.clip(cost, 0, 1))


def _snap_to_grid(lat: float, lon: float) -> Tuple[int, int]:
    """Convert lat/lon to grid indices."""
    grid_lat = round((lat - (-80)) / GRID_STEP)
    grid_lon = round((lon - (-180)) / GRID_STEP)
    return max(0, min(25, grid_lat)), max(0, min(360, grid_lon))


def _grid_to_latlon(gi: int, gj: int) -> Tuple[float, float]:
    lat = -80 + gi * GRID_STEP
    lon = -180 + gj * GRID_STEP
    return lat, lon


def _astar(
    start_lat: float, start_lon: float,
    end_lat: float, end_lon: float,
    weights: Dict[str, float]
) -> List[Tuple[float, float]]:
    """
    A* pathfinding on a geographic grid between two Antarctic points.
    Returns list of (lat, lon) waypoints.
    """
    si, sj = _snap_to_grid(start_lat, start_lon)
    ei, ej = _snap_to_grid(end_lat, end_lon)

    def heuristic(i, j):
        lat, lon = _grid_to_latlon(i, j)
        return _haversine_km(lat, lon, end_lat, end_lon) / 111.0  # normalized

    # Priority queue: (f_score, i, j)
    open_set = []
    heapq.heappush(open_set, (0, si, sj))

    came_from = {}
    g_score = {(si, sj): 0.0}
    f_score = {(si, sj): heuristic(si, sj)}

    visited = set()
    max_iterations = 2000

    for _ in range(max_iterations):
        if not open_set:
            break

        _, ci, cj = heapq.heappop(open_set)

        if (ci, cj) in visited:
            continue
        visited.add((ci, cj))

        if ci == ei and cj == ej:
            # Reconstruct path
            path = []
            node = (ci, cj)
            while node in came_from:
                lat, lon = _grid_to_latlon(node[0], node[1])
                path.append((lat, lon))
                node = came_from[node]
            lat, lon = _grid_to_latlon(si, sj)
            path.append((lat, lon))
            path.reverse()
            return path

        # Explore 8-connected neighbors
        for di in [-1, 0, 1]:
            for dj in [-1, 0, 1]:
                if di == 0 and dj == 0:
                    continue
                ni, nj = ci + di, cj + dj
                # Antarctic bounds: lat -80 to -55, lon wraps
                if ni < 0 or ni > 25:
                    continue
                nj = nj % 360  # longitude wraps

                if (ni, nj) in visited:
                    continue

                nlat, nlon = _grid_to_latlon(ni, nj)

                # Check if within Antarctic bounds
                if nlat > -55 or nlat < -80:
                    continue

                step_dist = _haversine_km(*_grid_to_latlon(ci, cj), nlat, nlon) / 111.0
                node_cost = _node_cost(nlat, nlon, weights)

                # Skip impassable cells
                if node_cost >= 5.0:
                    continue

                move_cost = step_dist * (
                    weights.get("distance", 0.3) +
                    weights.get("fuel", 0.2) * (1 + node_cost)
                ) + node_cost * 0.5

                tentative_g = g_score.get((ci, cj), float("inf")) + move_cost

                if tentative_g < g_score.get((ni, nj), float("inf")):
                    came_from[(ni, nj)] = (ci, cj)
                    g_score[(ni, nj)] = tentative_g
                    f = tentative_g + heuristic(ni, nj)
                    f_score[(ni, nj)] = f
                    heapq.heappush(open_set, (f, ni, nj))

    # Fallback: if A* doesn't find path, return great-circle straight line
    return _straight_line_path(start_lat, start_lon, end_lat, end_lon, n_points=12)


def _straight_line_path(lat1, lon1, lat2, lon2, n_points=12):
    """Fallback: interpolate straight line."""
    path = []
    for i in range(n_points):
        t = i / (n_points - 1)
        lat = lat1 + t * (lat2 - lat1)
        lon = lon1 + t * (lon2 - lon1)
        path.append((round(lat, 4), round(lon, 4)))
    return path


def _build_route(
    route_type: str,
    waypoints: List[Tuple[float, float]],
    origin_name: str,
    destination_name: str,
    vessel_speed_knots: float = 12.0,
) -> Dict:
    """Build a complete route result from A* waypoints."""
    now = datetime.now(timezone.utc)
    route_id = str(uuid.uuid4())

    # Calculate total distance
    total_dist_km = 0.0
    for i in range(1, len(waypoints)):
        total_dist_km += _haversine_km(
            waypoints[i-1][0], waypoints[i-1][1],
            waypoints[i][0], waypoints[i][1]
        )

    # Duration
    speed_kmh = vessel_speed_knots * 1.852
    duration_h = total_dist_km / speed_kmh if speed_kmh > 0 else 0

    # Fuel estimate (base consumption + ice penalty)
    base_fuel_day = 15.0  # tonnes/day
    avg_sic = float(np.mean([demo_service._sic_at(wp[0], wp[1]) for wp in waypoints]))
    ice_penalty = 1 + avg_sic * 0.8  # up to 80% more fuel in ice
    fuel_tonnes = (duration_h / 24.0) * base_fuel_day * ice_penalty

    # Risk assessment along route
    route_risks = []
    for lat, lon in waypoints[::2]:  # sample every other point
        risk_result = risk_service.calculate_risk(
            type("R", (), {"latitude": lat, "longitude": lon,
                           "radius_km": 50.0, "weights": None})()
        )
        route_risks.append(risk_result)

    avg_risk = float(np.mean([r["total_risk_score"] for r in route_risks])) if route_risks else 0.3
    max_sic = float(np.max([demo_service._sic_at(wp[0], wp[1]) for wp in waypoints]))
    iceberg_intersections = sum(
        1 for r in route_risks if r["iceberg_risk"] > 0.5
    )

    risk_cat = risk_service._risk_category(avg_risk)

    # Collect factors and recommendations
    all_factors = []
    all_recs = []
    for r in route_risks[:3]:
        for f in r["risk_factors"][:2]:
            if f["text"] not in all_factors:
                all_factors.append(f["text"])
        for rec in r["recommendations"][:1]:
            if rec not in all_recs:
                all_recs.append(rec)

    # Build waypoints list
    wp_list = []
    for seq, (lat, lon) in enumerate(waypoints):
        sic = demo_service._sic_at(lat, lon)
        seed = int(abs(lat * 100 + lon * 100)) % 99991
        rng = np.random.default_rng(seed)
        eta = now + timedelta(hours=(seq / len(waypoints)) * duration_h)
        wp_list.append({
            "sequence": seq,
            "latitude": round(lat, 4),
            "longitude": round(lon, 4),
            "sea_ice_concentration": round(sic, 3),
            "wind_speed_ms": round(float(rng.uniform(5, 18)), 2),
            "local_risk_score": round(demo_service._sic_at(lat, lon) * 0.6, 3),
            "estimated_arrival": eta.isoformat(),
        })

    result = {
        "id": route_id,
        "route_type": route_type,
        "origin_name": origin_name,
        "destination_name": destination_name,
        "waypoints": wp_list,
        "total_distance_km": round(total_dist_km, 1),
        "estimated_duration_hours": round(duration_h, 1),
        "estimated_fuel_tonnes": round(fuel_tonnes, 1),
        "fuel_efficiency_index": round(fuel_tonnes / max(fuel_tonnes, 1), 3),  # normalized later
        "overall_risk_score": round(avg_risk, 3),
        "sea_ice_risk_score": round(
            float(np.mean([r["sea_ice_risk"] for r in route_risks])) if route_risks else avg_sic, 3
        ),
        "iceberg_risk_score": round(
            float(np.mean([r["iceberg_risk"] for r in route_risks])) if route_risks else 0.2, 3
        ),
        "weather_risk_score": round(
            float(np.mean([r["weather_risk"] for r in route_risks])) if route_risks else 0.3, 3
        ),
        "ocean_risk_score": round(
            float(np.mean([r["ocean_risk"] for r in route_risks])) if route_risks else 0.2, 3
        ),
        "risk_category": risk_cat,
        "max_ice_concentration": round(max_sic, 3),
        "avg_ice_concentration": round(avg_sic, 3),
        "iceberg_intersections": iceberg_intersections,
        "risk_factors": all_factors[:6],
        "recommendations": all_recs[:3] or ["Proceed with standard polar navigation precautions"],
        "data_mode": "demo",
    }

    # Cache for GET /routes/{id}
    _route_cache[route_id] = result
    return result


def generate_routes(request) -> Dict:
    """Generate route(s) based on preference."""
    now = datetime.now(timezone.utc)
    routes = []

    if request.generate_all:
        for rtype in ["shortest", "safest", "fuel_efficient", "balanced"]:
            weights = ROUTE_WEIGHTS[rtype]
            wps = _astar(
                request.origin_lat, request.origin_lon,
                request.destination_lat, request.destination_lon,
                weights
            )
            route = _build_route(
                rtype, wps,
                request.origin_name or "Origin",
                request.destination_name or "Destination"
            )
            routes.append(route)
    else:
        weights = ROUTE_WEIGHTS.get(request.route_preference, ROUTE_WEIGHTS["balanced"])
        wps = _astar(
            request.origin_lat, request.origin_lon,
            request.destination_lat, request.destination_lon,
            weights
        )
        route = _build_route(
            request.route_preference, wps,
            request.origin_name or "Origin",
            request.destination_name or "Destination"
        )
        routes.append(route)

    # Normalize fuel efficiency index relative to shortest route
    if routes:
        min_fuel = min(r["estimated_fuel_tonnes"] for r in routes)
        for r in routes:
            r["fuel_efficiency_index"] = round(r["estimated_fuel_tonnes"] / max(min_fuel, 0.1), 3)

    return {
        "generated_at": now.isoformat(),
        "origin_name": request.origin_name or "Origin",
        "destination_name": request.destination_name or "Destination",
        "routes": routes,
        "data_mode": "demo",
    }


def compare_routes(request) -> Dict:
    """Generate all route types and provide comparison + recommendation."""
    now = datetime.now(timezone.utc)
    routes = []

    for rtype in ["shortest", "safest", "fuel_efficient", "balanced"]:
        weights = ROUTE_WEIGHTS[rtype]
        wps = _astar(
            request.origin_lat, request.origin_lon,
            request.destination_lat, request.destination_lon,
            weights
        )
        route = _build_route(
            rtype, wps,
            request.origin_name or "Origin",
            request.destination_name or "Destination"
        )
        routes.append(route)

    # Normalize fuel efficiency
    min_fuel = min(r["estimated_fuel_tonnes"] for r in routes)
    for r in routes:
        r["fuel_efficiency_index"] = round(r["estimated_fuel_tonnes"] / max(min_fuel, 0.1), 3)

    # Recommend safest viable route
    safest = min(routes, key=lambda r: r["overall_risk_score"])
    recommended = safest["route_type"]
    recommendation_reason = (
        f"Route '{safest['route_type']}' has the lowest predicted risk score "
        f"({safest['overall_risk_score']*100:.0f}/100). "
        f"It is {safest['total_distance_km']:.0f} km long with "
        f"an estimated {safest['estimated_duration_hours']:.0f} h transit time. "
        f"Average sea-ice concentration along route: {safest['avg_ice_concentration']*100:.0f}%. "
        f"Risk category: {safest['risk_category'].upper()}."
    )

    return {
        "generated_at": now.isoformat(),
        "origin_name": request.origin_name or "Origin",
        "destination_name": request.destination_name or "Destination",
        "routes": routes,
        "recommended_route_type": recommended,
        "recommendation_reason": recommendation_reason,
        "data_mode": "demo",
    }


def get_route_by_id(route_id: str) -> Optional[Dict]:
    """Retrieve a cached route by ID."""
    return _route_cache.get(route_id)


def replan_route(route_id: str, reason: str) -> Dict:
    """Dynamically replan a route due to changed conditions."""
    existing = _route_cache.get(route_id)
    if not existing:
        return None

    # Recalculate with safest weights
    wps = _astar(
        existing["waypoints"][0]["latitude"],
        existing["waypoints"][0]["longitude"],
        existing["waypoints"][-1]["latitude"],
        existing["waypoints"][-1]["longitude"],
        ROUTE_WEIGHTS["safest"]
    )
    new_route = _build_route(
        "replanned_safe",
        wps,
        existing["origin_name"],
        existing["destination_name"]
    )
    new_route["recalculation_count"] = existing.get("recalculation_count", 0) + 1
    new_route["recalculation_reason"] = reason
    return new_route
