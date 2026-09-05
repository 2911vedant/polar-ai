from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import uuid


class IcebergSummary(BaseModel):
    id: str
    iceberg_name: str
    latitude: float
    longitude: float
    length_km: Optional[float]
    width_km: Optional[float]
    area_km2: Optional[float]
    drift_speed_kmh: Optional[float]
    drift_direction_deg: Optional[float]
    risk_level: str
    status: str
    last_observed_at: Optional[datetime]
    data_mode: str


class IcebergPosition(BaseModel):
    observed_at: datetime
    latitude: float
    longitude: float
    speed_kmh: Optional[float]
    direction_deg: Optional[float]
    confidence: float


class IcebergDetail(BaseModel):
    id: str
    iceberg_name: str
    latitude: float
    longitude: float
    length_km: Optional[float]
    width_km: Optional[float]
    area_km2: Optional[float]
    drift_speed_kmh: Optional[float]
    drift_direction_deg: Optional[float]
    risk_level: str
    status: str
    source: str
    last_observed_at: Optional[datetime]
    positions: List[IcebergPosition]
    data_mode: str


class TrajectoryPoint(BaseModel):
    horizon_hours: int
    valid_time: datetime
    latitude: float
    longitude: float
    uncertainty_km: Optional[float]
    confidence: float


class IcebergTrajectoryResponse(BaseModel):
    iceberg_id: str
    iceberg_name: str
    current_lat: float
    current_lon: float
    predicted_at: datetime
    trajectory: List[TrajectoryPoint]
    model_name: str
    # Closest approach to vessel
    closest_approach_km: Optional[float]
    closest_approach_time: Optional[datetime]
    data_mode: str


class IcebergsListResponse(BaseModel):
    icebergs: List[IcebergSummary]
    total_count: int
    active_count: int
    high_risk_count: int
    data_mode: str


class TrajectoryPredictRequest(BaseModel):
    latitude: float
    longitude: float
    horizon_hours: int = Field(default=72, ge=1, le=168)
    wind_speed_ms: Optional[float] = None
    wind_direction_deg: Optional[float] = None
    ocean_current_u: Optional[float] = None
    ocean_current_v: Optional[float] = None
    iceberg_name: Optional[str] = None
