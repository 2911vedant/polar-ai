"""
POLAR-AI Weather Models
"""
from sqlalchemy import Column, Float, Integer, String, DateTime
from geoalchemy2 import Geometry
from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class WeatherObservation(Base, UUIDMixin, TimestampMixin):
    """
    Meteorological observation or forecast at a grid point.
    Sourced from ERA5 reanalysis or synthetic demo data.
    """
    __tablename__ = "weather_observations"

    observation_time = Column(DateTime(timezone=True), nullable=False, index=True)
    forecast_valid_time = Column(DateTime(timezone=True))  # null = observation, not forecast

    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    location = Column(Geometry("POINT", srid=4326))

    # Wind
    wind_speed_ms = Column(Float)       # m/s
    wind_direction_deg = Column(Float)  # 0-360
    wind_u_ms = Column(Float)           # eastward component
    wind_v_ms = Column(Float)           # northward component

    # Temperature & Pressure
    air_temp_celsius = Column(Float)
    sea_level_pressure_hpa = Column(Float)
    surface_pressure_hpa = Column(Float)

    # Precipitation
    precipitation_mm = Column(Float)

    # Visibility / conditions
    visibility_km = Column(Float)
    weather_code = Column(Integer)  # WMO weather code

    # Risk contribution
    weather_risk_score = Column(Float)  # 0.0 - 1.0

    source = Column(String(50), default="demo")  # era5 | demo
    data_mode = Column(String(10), default="demo")
