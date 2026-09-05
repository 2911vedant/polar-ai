from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class WeatherPoint(BaseModel):
    latitude: float
    longitude: float
    wind_speed_ms: float
    wind_direction_deg: float
    air_temp_celsius: float
    sea_level_pressure_hpa: float
    precipitation_mm: Optional[float] = 0.0
    weather_risk_score: float
    source: str


class WeatherCurrentResponse(BaseModel):
    timestamp: datetime
    grid_points: List[WeatherPoint]
    avg_wind_speed_ms: float
    min_temp_celsius: float
    data_mode: str


class WeatherForecastPoint(BaseModel):
    valid_time: datetime
    horizon_hours: int
    latitude: float
    longitude: float
    wind_speed_ms: float
    wind_direction_deg: float
    air_temp_celsius: float
    sea_level_pressure_hpa: float
    weather_risk_score: float


class WeatherForecastResponse(BaseModel):
    generated_at: datetime
    forecast_points: List[WeatherForecastPoint]
    data_mode: str
