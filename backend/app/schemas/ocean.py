from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class OceanPoint(BaseModel):
    latitude: float
    longitude: float
    current_speed_ms: float
    current_direction_deg: float
    current_u_ms: float
    current_v_ms: float
    sea_surface_temp_celsius: float
    significant_wave_height_m: Optional[float] = None
    ocean_risk_score: float
    source: str


class OceanCurrentResponse(BaseModel):
    timestamp: datetime
    grid_points: List[OceanPoint]
    avg_current_speed_ms: float
    avg_sst_celsius: float
    data_mode: str
