"""
POLAR-AI Sea Ice Models
Database tables for sea-ice observations and forecasts.
"""
from sqlalchemy import Column, Float, Integer, String, DateTime, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geometry
import uuid
from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class SeaIceObservation(Base, UUIDMixin, TimestampMixin):
    """
    Historical sea-ice concentration observation from satellite data.
    Each row represents a grid cell at a specific timestamp.
    """
    __tablename__ = "sea_ice_observations"

    observation_time = Column(DateTime(timezone=True), nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    location = Column(Geometry("POINT", srid=4326))

    # Sea ice concentration 0.0 - 1.0
    concentration = Column(Float, nullable=False)

    # Source metadata
    source = Column(String(100), default="demo")  # nsidc_g02135 | nsidc_g02202 | demo
    satellite = Column(String(50))
    quality_flag = Column(Integer, default=0)  # 0=good, 1=suspect, 2=bad

    # Grid cell info
    grid_x = Column(Integer)
    grid_y = Column(Integer)
    grid_resolution_km = Column(Float, default=25.0)

    # Derived categories
    ice_category = Column(String(20))  # open_water | low | moderate | high | consolidated


class SeaIceForecast(Base, UUIDMixin, TimestampMixin):
    """
    ML-generated sea-ice concentration forecast.
    """
    __tablename__ = "sea_ice_forecasts"

    # When this forecast was generated
    forecast_generated_at = Column(DateTime(timezone=True), nullable=False)
    # What time the forecast is for
    forecast_valid_time = Column(DateTime(timezone=True), nullable=False, index=True)
    # Forecast horizon in hours
    horizon_hours = Column(Integer, nullable=False)  # 24, 48, 72, 168

    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    location = Column(Geometry("POINT", srid=4326))

    # Predicted concentration 0.0 - 1.0
    predicted_concentration = Column(Float, nullable=False)
    # Model uncertainty / confidence
    uncertainty = Column(Float)
    confidence = Column(Float)  # 0.0 - 1.0

    # Model info
    model_name = Column(String(50), default="rf_baseline")
    model_version = Column(String(20), default="1.0")

    # Grid metadata
    grid_x = Column(Integer)
    grid_y = Column(Integer)

    # Risk category derived from concentration
    risk_category = Column(String(20))  # low | moderate | high | extreme
