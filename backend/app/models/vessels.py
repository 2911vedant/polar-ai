"""
POLAR-AI Vessel Models
"""
from sqlalchemy import Column, Float, Integer, String, DateTime, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geometry
from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class Vessel(Base, UUIDMixin, TimestampMixin):
    """
    Research vessel registry.
    """
    __tablename__ = "vessels"

    name = Column(String(100), nullable=False)
    vessel_type = Column(String(50), default="research")
    imo_number = Column(String(20))
    flag = Column(String(50))

    # Physical characteristics
    length_m = Column(Float)
    beam_m = Column(Float)
    draft_m = Column(Float)
    displacement_tonnes = Column(Float)

    # Propulsion
    max_speed_knots = Column(Float, default=15.0)
    cruise_speed_knots = Column(Float, default=12.0)
    fuel_capacity_tonnes = Column(Float)
    fuel_consumption_tonnes_per_day = Column(Float)

    # Ice capability
    ice_class = Column(String(20), default="1A")  # 1A, 1B, PC4, PC3 etc.
    max_ice_concentration = Column(Float, default=0.7)  # max SIC navigable

    # Current state
    current_lat = Column(Float)
    current_lon = Column(Float)
    current_location = Column(Geometry("POINT", srid=4326))
    current_speed_knots = Column(Float)
    current_heading_deg = Column(Float)
    current_status = Column(String(30), default="underway")

    is_active = Column(Boolean, default=True)
    data_mode = Column(String(10), default="demo")
