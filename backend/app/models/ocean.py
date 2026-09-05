"""
POLAR-AI Ocean Models
"""
from sqlalchemy import Column, Float, Integer, String, DateTime
from geoalchemy2 import Geometry
from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class OceanObservation(Base, UUIDMixin, TimestampMixin):
    """
    Oceanographic observation at a grid point.
    Sourced from Copernicus Marine Service or synthetic demo data.
    """
    __tablename__ = "ocean_observations"

    observation_time = Column(DateTime(timezone=True), nullable=False, index=True)

    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    location = Column(Geometry("POINT", srid=4326))
    depth_m = Column(Float, default=0.0)

    # Ocean currents
    current_speed_ms = Column(Float)     # m/s total speed
    current_direction_deg = Column(Float) # 0-360
    current_u_ms = Column(Float)         # eastward component
    current_v_ms = Column(Float)         # northward component

    # Temperature & salinity
    sea_surface_temp_celsius = Column(Float)
    salinity_psu = Column(Float)

    # Wave conditions
    significant_wave_height_m = Column(Float)
    wave_period_s = Column(Float)
    wave_direction_deg = Column(Float)

    # Risk contribution
    ocean_risk_score = Column(Float)  # 0.0 - 1.0

    source = Column(String(50), default="demo")  # cmems | demo
    data_mode = Column(String(10), default="demo")
