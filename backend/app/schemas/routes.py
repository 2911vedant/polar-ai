from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class RouteWaypoint(BaseModel):
    sequence: int
    latitude: float
    longitude: float
    sea_ice_concentration: Optional[float] = None
    wind_speed_ms: Optional[float] = None
    local_risk_score: Optional[float] = None
    estimated_arrival: Optional[datetime] = None


class RouteResult(BaseModel):
    id: str
    route_type: str       # shortest | safest | fuel_efficient | balanced
    origin_name: str
    destination_name: str
    waypoints: List[RouteWaypoint]
    total_distance_km: float
    estimated_duration_hours: float
    estimated_fuel_tonnes: float
    fuel_efficiency_index: float  # relative (1.0 = baseline/shortest)
    overall_risk_score: float
    sea_ice_risk_score: float
    iceberg_risk_score: float
    weather_risk_score: float
    ocean_risk_score: float
    risk_category: str
    max_ice_concentration: float
    avg_ice_concentration: float
    iceberg_intersections: int
    risk_factors: List[str]
    recommendations: List[str]
    data_mode: str


class RouteGenerateRequest(BaseModel):
    origin_lat: float
    origin_lon: float
    origin_name: Optional[str] = "Origin"
    destination_lat: float
    destination_lon: float
    destination_name: Optional[str] = "Destination"
    vessel_name: Optional[str] = "RV Polar Explorer"
    departure_time: Optional[datetime] = None
    route_preference: str = Field(default="balanced")  # shortest | safest | fuel_efficient | balanced
    generate_all: bool = Field(default=True)  # generate all 4 types for comparison


class RouteCompareRequest(BaseModel):
    origin_lat: float
    origin_lon: float
    destination_lat: float
    destination_lon: float
    origin_name: Optional[str] = "Origin"
    destination_name: Optional[str] = "Destination"


class RouteCompareResponse(BaseModel):
    generated_at: datetime
    origin_name: str
    destination_name: str
    routes: List[RouteResult]
    recommended_route_type: str
    recommendation_reason: str
    data_mode: str


class RiskCalculateRequest(BaseModel):
    latitude: float
    longitude: float
    radius_km: float = Field(default=50.0, ge=1.0, le=500.0)
    weights: Optional[Dict[str, float]] = None  # override default weights


class RiskCalculateResponse(BaseModel):
    latitude: float
    longitude: float
    radius_km: float
    assessed_at: datetime
    sea_ice_risk: float
    iceberg_risk: float
    weather_risk: float
    ocean_risk: float
    total_risk_score: float
    risk_category: str
    risk_factors: List[Dict[str, Any]]
    recommendations: List[str]
    data_mode: str
