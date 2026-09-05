from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class SeaIceGridPoint(BaseModel):
    latitude: float
    longitude: float
    concentration: float = Field(..., ge=0.0, le=1.0)
    ice_category: str  # open_water | low | moderate | high | consolidated
    grid_x: Optional[int] = None
    grid_y: Optional[int] = None


class SeaIceCurrentResponse(BaseModel):
    timestamp: datetime
    grid_points: List[SeaIceGridPoint]
    coverage_pct: float  # % of Antarctic region with SIC > 15%
    extent_km2: float
    source: str
    data_mode: str


class SeaIceForecastPoint(BaseModel):
    latitude: float
    longitude: float
    predicted_concentration: float = Field(..., ge=0.0, le=1.0)
    uncertainty: float
    confidence: float
    risk_category: str


class SeaIceForecastResponse(BaseModel):
    generated_at: datetime
    valid_time: datetime
    horizon_hours: int  # 24, 48, 72, 168
    grid_points: List[SeaIceForecastPoint]
    model_name: str
    overall_confidence: float
    mae: Optional[float] = None
    rmse: Optional[float] = None
    data_mode: str


class SeaIcePredictRequest(BaseModel):
    horizon_hours: int = Field(default=24, ge=1, le=168)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    bounding_box: Optional[dict] = None


class SeaIceHistoryPoint(BaseModel):
    date: datetime
    coverage_pct: float
    extent_km2: float
    anomaly_pct: Optional[float] = None


class SeaIceHistoryResponse(BaseModel):
    start_date: datetime
    end_date: datetime
    data_points: List[SeaIceHistoryPoint]
    source: str
    data_mode: str
