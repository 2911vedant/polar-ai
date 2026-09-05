"""
POLAR-AI Route Models
"""
from sqlalchemy import Column, Float, Integer, String, DateTime, Boolean, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class Route(Base, UUIDMixin, TimestampMixin):
    """
    A computed navigation route from origin to destination.
    """
    __tablename__ = "routes"

    # Route identity
    name = Column(String(100))
    route_type = Column(String(30), nullable=False)  # shortest | safest | fuel_efficient | balanced

    # Endpoints
    origin_lat = Column(Float, nullable=False)
    origin_lon = Column(Float, nullable=False)
    origin_name = Column(String(100))
    destination_lat = Column(Float, nullable=False)
    destination_lon = Column(Float, nullable=False)
    destination_name = Column(String(100))

    # Route geometry (full path)
    route_geometry = Column(Geometry("LINESTRING", srid=4326))

    # Route metrics
    total_distance_km = Column(Float)
    estimated_duration_hours = Column(Float)
    estimated_fuel_tonnes = Column(Float)
    fuel_efficiency_index = Column(Float)  # relative to shortest (1.0 = baseline)

    # Risk metrics
    overall_risk_score = Column(Float)       # 0.0 - 1.0
    sea_ice_risk_score = Column(Float)
    iceberg_risk_score = Column(Float)
    weather_risk_score = Column(Float)
    ocean_risk_score = Column(Float)
    risk_category = Column(String(20))       # low | moderate | high | extreme

    # Exposure metrics
    max_ice_concentration = Column(Float)
    avg_ice_concentration = Column(Float)
    iceberg_intersections = Column(Integer, default=0)

    # Routing algorithm info
    algorithm = Column(String(20), default="astar")
    cost_weights = Column(JSON)  # {distance, fuel, ice, iceberg, weather}

    # Vessel
    vessel_id = Column(UUID(as_uuid=True), ForeignKey("vessels.id"))
    departure_time = Column(DateTime(timezone=True))

    # Status
    status = Column(String(20), default="planned")  # planned | active | completed | cancelled
    is_current = Column(Boolean, default=False)

    # Recalculation tracking
    recalculation_count = Column(Integer, default=0)
    recalculation_reason = Column(String(200))

    data_mode = Column(String(10), default="demo")

    # Relationships
    waypoints = relationship("RoutePoint", back_populates="route", order_by="RoutePoint.sequence_number")
    risk_assessments = relationship("RiskAssessment", back_populates="route")


class RoutePoint(Base, UUIDMixin, TimestampMixin):
    """
    Individual waypoint in a route.
    """
    __tablename__ = "route_points"

    route_id = Column(UUID(as_uuid=True), ForeignKey("routes.id"), nullable=False, index=True)
    sequence_number = Column(Integer, nullable=False)

    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    location = Column(Geometry("POINT", srid=4326))

    # Conditions at this waypoint
    sea_ice_concentration = Column(Float)
    wind_speed_ms = Column(Float)
    current_speed_ms = Column(Float)
    local_risk_score = Column(Float)

    # ETA at this waypoint
    estimated_arrival = Column(DateTime(timezone=True))

    route = relationship("Route", back_populates="waypoints")


class RiskAssessment(Base, UUIDMixin, TimestampMixin):
    """
    Detailed risk assessment for a route or region.
    """
    __tablename__ = "risk_assessments"

    route_id = Column(UUID(as_uuid=True), ForeignKey("routes.id"), index=True)
    assessed_at = Column(DateTime(timezone=True))

    # Location of assessment
    latitude = Column(Float)
    longitude = Column(Float)
    location = Column(Geometry("POINT", srid=4326))

    # Component scores (0.0 - 1.0)
    sea_ice_risk = Column(Float, default=0.0)
    iceberg_risk = Column(Float, default=0.0)
    weather_risk = Column(Float, default=0.0)
    ocean_risk = Column(Float, default=0.0)

    # Weights used
    w_sea_ice = Column(Float, default=0.35)
    w_iceberg = Column(Float, default=0.30)
    w_weather = Column(Float, default=0.20)
    w_ocean = Column(Float, default=0.15)

    # Combined
    total_risk_score = Column(Float, nullable=False)
    risk_category = Column(String(20))

    # Explanations
    risk_factors = Column(JSON)  # list of contributing factors with descriptions
    recommendations = Column(JSON)  # list of recommendation strings

    data_mode = Column(String(10), default="demo")

    route = relationship("Route", back_populates="risk_assessments")
