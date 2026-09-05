"""Initial POLAR-AI schema

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
import geoalchemy2
from sqlalchemy.dialects.postgresql import UUID

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable PostGIS if not done by init script
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # ── system_events ──────────────────────────────────────────────────────────
    op.create_table('system_events',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('message', sa.String(500)),
        sa.Column('severity', sa.String(20), server_default='info'),
        sa.Column('source', sa.String(100)),
        sa.Column('data', sa.String(2000)),
    )

    # ── vessels ────────────────────────────────────────────────────────────────
    op.create_table('vessels',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('vessel_type', sa.String(50), server_default='research'),
        sa.Column('imo_number', sa.String(20)),
        sa.Column('flag', sa.String(50)),
        sa.Column('length_m', sa.Float()),
        sa.Column('beam_m', sa.Float()),
        sa.Column('draft_m', sa.Float()),
        sa.Column('displacement_tonnes', sa.Float()),
        sa.Column('max_speed_knots', sa.Float(), server_default='15.0'),
        sa.Column('cruise_speed_knots', sa.Float(), server_default='12.0'),
        sa.Column('fuel_capacity_tonnes', sa.Float()),
        sa.Column('fuel_consumption_tonnes_per_day', sa.Float()),
        sa.Column('ice_class', sa.String(20), server_default='1A'),
        sa.Column('max_ice_concentration', sa.Float(), server_default='0.7'),
        sa.Column('current_lat', sa.Float()),
        sa.Column('current_lon', sa.Float()),
        sa.Column('current_location', geoalchemy2.types.Geometry('POINT', srid=4326)),
        sa.Column('current_speed_knots', sa.Float()),
        sa.Column('current_heading_deg', sa.Float()),
        sa.Column('current_status', sa.String(30), server_default='underway'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('data_mode', sa.String(10), server_default='demo'),
    )

    # ── sea_ice_observations ───────────────────────────────────────────────────
    op.create_table('sea_ice_observations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('observation_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('location', geoalchemy2.types.Geometry('POINT', srid=4326)),
        sa.Column('concentration', sa.Float(), nullable=False),
        sa.Column('source', sa.String(100), server_default='demo'),
        sa.Column('satellite', sa.String(50)),
        sa.Column('quality_flag', sa.Integer(), server_default='0'),
        sa.Column('grid_x', sa.Integer()),
        sa.Column('grid_y', sa.Integer()),
        sa.Column('grid_resolution_km', sa.Float(), server_default='25.0'),
        sa.Column('ice_category', sa.String(20)),
    )
    op.create_index('ix_sea_ice_obs_time', 'sea_ice_observations', ['observation_time'])

    # ── sea_ice_forecasts ──────────────────────────────────────────────────────
    op.create_table('sea_ice_forecasts',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('forecast_generated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('forecast_valid_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('horizon_hours', sa.Integer(), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('location', geoalchemy2.types.Geometry('POINT', srid=4326)),
        sa.Column('predicted_concentration', sa.Float(), nullable=False),
        sa.Column('uncertainty', sa.Float()),
        sa.Column('confidence', sa.Float()),
        sa.Column('model_name', sa.String(50), server_default='rf_baseline'),
        sa.Column('model_version', sa.String(20), server_default='1.0'),
        sa.Column('grid_x', sa.Integer()),
        sa.Column('grid_y', sa.Integer()),
        sa.Column('risk_category', sa.String(20)),
    )
    op.create_index('ix_sea_ice_forecast_valid_time', 'sea_ice_forecasts', ['forecast_valid_time'])

    # ── icebergs ───────────────────────────────────────────────────────────────
    op.create_table('icebergs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('iceberg_name', sa.String(50), nullable=False, unique=True),
        sa.Column('source', sa.String(100), server_default='demo'),
        sa.Column('last_known_lat', sa.Float()),
        sa.Column('last_known_lon', sa.Float()),
        sa.Column('last_known_location', geoalchemy2.types.Geometry('POINT', srid=4326)),
        sa.Column('last_observed_at', sa.DateTime(timezone=True)),
        sa.Column('length_km', sa.Float()),
        sa.Column('width_km', sa.Float()),
        sa.Column('area_km2', sa.Float()),
        sa.Column('status', sa.String(30), server_default='active'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('drift_speed_kmh', sa.Float()),
        sa.Column('drift_direction_deg', sa.Float()),
        sa.Column('risk_level', sa.String(20), server_default='low'),
        sa.Column('threat_to_vessel', sa.Boolean(), server_default='false'),
        sa.Column('data_mode', sa.String(10), server_default='demo'),
    )
    op.create_index('ix_icebergs_name', 'icebergs', ['iceberg_name'])

    # ── iceberg_positions ──────────────────────────────────────────────────────
    op.create_table('iceberg_positions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('iceberg_id', UUID(as_uuid=True), sa.ForeignKey('icebergs.id'), nullable=False),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('location', geoalchemy2.types.Geometry('POINT', srid=4326)),
        sa.Column('length_km', sa.Float()),
        sa.Column('width_km', sa.Float()),
        sa.Column('area_km2', sa.Float()),
        sa.Column('speed_kmh', sa.Float()),
        sa.Column('direction_deg', sa.Float()),
        sa.Column('source', sa.String(50), server_default='demo'),
        sa.Column('confidence', sa.Float(), server_default='1.0'),
    )
    op.create_index('ix_iceberg_positions_iceberg_id', 'iceberg_positions', ['iceberg_id'])
    op.create_index('ix_iceberg_positions_observed_at', 'iceberg_positions', ['observed_at'])

    # ── iceberg_trajectory_predictions ────────────────────────────────────────
    op.create_table('iceberg_trajectory_predictions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('iceberg_id', UUID(as_uuid=True), sa.ForeignKey('icebergs.id'), nullable=False),
        sa.Column('predicted_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('valid_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('horizon_hours', sa.Integer(), nullable=False),
        sa.Column('predicted_lat', sa.Float(), nullable=False),
        sa.Column('predicted_lon', sa.Float(), nullable=False),
        sa.Column('predicted_location', geoalchemy2.types.Geometry('POINT', srid=4326)),
        sa.Column('uncertainty_major_km', sa.Float()),
        sa.Column('uncertainty_minor_km', sa.Float()),
        sa.Column('uncertainty_bearing_deg', sa.Float()),
        sa.Column('confidence', sa.Float()),
        sa.Column('model_name', sa.String(50), server_default='physics_baseline'),
    )

    # ── weather_observations ───────────────────────────────────────────────────
    op.create_table('weather_observations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('observation_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('forecast_valid_time', sa.DateTime(timezone=True)),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('location', geoalchemy2.types.Geometry('POINT', srid=4326)),
        sa.Column('wind_speed_ms', sa.Float()),
        sa.Column('wind_direction_deg', sa.Float()),
        sa.Column('wind_u_ms', sa.Float()),
        sa.Column('wind_v_ms', sa.Float()),
        sa.Column('air_temp_celsius', sa.Float()),
        sa.Column('sea_level_pressure_hpa', sa.Float()),
        sa.Column('surface_pressure_hpa', sa.Float()),
        sa.Column('precipitation_mm', sa.Float()),
        sa.Column('visibility_km', sa.Float()),
        sa.Column('weather_code', sa.Integer()),
        sa.Column('weather_risk_score', sa.Float()),
        sa.Column('source', sa.String(50), server_default='demo'),
        sa.Column('data_mode', sa.String(10), server_default='demo'),
    )
    op.create_index('ix_weather_obs_time', 'weather_observations', ['observation_time'])

    # ── ocean_observations ─────────────────────────────────────────────────────
    op.create_table('ocean_observations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('observation_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('location', geoalchemy2.types.Geometry('POINT', srid=4326)),
        sa.Column('depth_m', sa.Float(), server_default='0.0'),
        sa.Column('current_speed_ms', sa.Float()),
        sa.Column('current_direction_deg', sa.Float()),
        sa.Column('current_u_ms', sa.Float()),
        sa.Column('current_v_ms', sa.Float()),
        sa.Column('sea_surface_temp_celsius', sa.Float()),
        sa.Column('salinity_psu', sa.Float()),
        sa.Column('significant_wave_height_m', sa.Float()),
        sa.Column('wave_period_s', sa.Float()),
        sa.Column('wave_direction_deg', sa.Float()),
        sa.Column('ocean_risk_score', sa.Float()),
        sa.Column('source', sa.String(50), server_default='demo'),
        sa.Column('data_mode', sa.String(10), server_default='demo'),
    )
    op.create_index('ix_ocean_obs_time', 'ocean_observations', ['observation_time'])

    # ── routes ─────────────────────────────────────────────────────────────────
    op.create_table('routes',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('name', sa.String(100)),
        sa.Column('route_type', sa.String(30), nullable=False),
        sa.Column('origin_lat', sa.Float(), nullable=False),
        sa.Column('origin_lon', sa.Float(), nullable=False),
        sa.Column('origin_name', sa.String(100)),
        sa.Column('destination_lat', sa.Float(), nullable=False),
        sa.Column('destination_lon', sa.Float(), nullable=False),
        sa.Column('destination_name', sa.String(100)),
        sa.Column('route_geometry', geoalchemy2.types.Geometry('LINESTRING', srid=4326)),
        sa.Column('total_distance_km', sa.Float()),
        sa.Column('estimated_duration_hours', sa.Float()),
        sa.Column('estimated_fuel_tonnes', sa.Float()),
        sa.Column('fuel_efficiency_index', sa.Float()),
        sa.Column('overall_risk_score', sa.Float()),
        sa.Column('sea_ice_risk_score', sa.Float()),
        sa.Column('iceberg_risk_score', sa.Float()),
        sa.Column('weather_risk_score', sa.Float()),
        sa.Column('ocean_risk_score', sa.Float()),
        sa.Column('risk_category', sa.String(20)),
        sa.Column('max_ice_concentration', sa.Float()),
        sa.Column('avg_ice_concentration', sa.Float()),
        sa.Column('iceberg_intersections', sa.Integer(), server_default='0'),
        sa.Column('algorithm', sa.String(20), server_default='astar'),
        sa.Column('cost_weights', sa.JSON()),
        sa.Column('vessel_id', UUID(as_uuid=True), sa.ForeignKey('vessels.id')),
        sa.Column('departure_time', sa.DateTime(timezone=True)),
        sa.Column('status', sa.String(20), server_default='planned'),
        sa.Column('is_current', sa.Boolean(), server_default='false'),
        sa.Column('recalculation_count', sa.Integer(), server_default='0'),
        sa.Column('recalculation_reason', sa.String(200)),
        sa.Column('data_mode', sa.String(10), server_default='demo'),
    )

    # ── route_points ───────────────────────────────────────────────────────────
    op.create_table('route_points',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('route_id', UUID(as_uuid=True), sa.ForeignKey('routes.id'), nullable=False),
        sa.Column('sequence_number', sa.Integer(), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('location', geoalchemy2.types.Geometry('POINT', srid=4326)),
        sa.Column('sea_ice_concentration', sa.Float()),
        sa.Column('wind_speed_ms', sa.Float()),
        sa.Column('current_speed_ms', sa.Float()),
        sa.Column('local_risk_score', sa.Float()),
        sa.Column('estimated_arrival', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_route_points_route_id', 'route_points', ['route_id'])

    # ── risk_assessments ───────────────────────────────────────────────────────
    op.create_table('risk_assessments',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('route_id', UUID(as_uuid=True), sa.ForeignKey('routes.id')),
        sa.Column('assessed_at', sa.DateTime(timezone=True)),
        sa.Column('latitude', sa.Float()),
        sa.Column('longitude', sa.Float()),
        sa.Column('location', geoalchemy2.types.Geometry('POINT', srid=4326)),
        sa.Column('sea_ice_risk', sa.Float(), server_default='0.0'),
        sa.Column('iceberg_risk', sa.Float(), server_default='0.0'),
        sa.Column('weather_risk', sa.Float(), server_default='0.0'),
        sa.Column('ocean_risk', sa.Float(), server_default='0.0'),
        sa.Column('w_sea_ice', sa.Float(), server_default='0.35'),
        sa.Column('w_iceberg', sa.Float(), server_default='0.30'),
        sa.Column('w_weather', sa.Float(), server_default='0.20'),
        sa.Column('w_ocean', sa.Float(), server_default='0.15'),
        sa.Column('total_risk_score', sa.Float(), nullable=False),
        sa.Column('risk_category', sa.String(20)),
        sa.Column('risk_factors', sa.JSON()),
        sa.Column('recommendations', sa.JSON()),
        sa.Column('data_mode', sa.String(10), server_default='demo'),
    )

    # ── Spatial indexes ─────────────────────────────────────────────────────────
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_sea_ice_obs_location
        ON sea_ice_observations USING GIST (location)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_sea_ice_forecast_location
        ON sea_ice_forecasts USING GIST (location)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_icebergs_location
        ON icebergs USING GIST (last_known_location)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_iceberg_positions_location
        ON iceberg_positions USING GIST (location)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_routes_geometry
        ON routes USING GIST (route_geometry)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_risk_assessments_location
        ON risk_assessments USING GIST (location)
    """)


def downgrade() -> None:
    op.drop_table('risk_assessments')
    op.drop_table('route_points')
    op.drop_table('routes')
    op.drop_table('ocean_observations')
    op.drop_table('weather_observations')
    op.drop_table('iceberg_trajectory_predictions')
    op.drop_table('iceberg_positions')
    op.drop_table('icebergs')
    op.drop_table('sea_ice_forecasts')
    op.drop_table('sea_ice_observations')
    op.drop_table('vessels')
    op.drop_table('system_events')
