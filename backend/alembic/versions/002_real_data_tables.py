"""Add vessel tracking, satellite products, alerts tables

Revision ID: 002
Revises: 001
Create Date: 2024-01-02 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
import geoalchemy2
from sqlalchemy.dialects.postgresql import UUID

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── vessel_positions ───────────────────────────────────────────────────────
    op.create_table('vessel_positions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('vessel_name', sa.String(100)),
        sa.Column('mmsi', sa.String(20), index=True),
        sa.Column('imo', sa.String(20)),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('location', geoalchemy2.types.Geometry('POINT', srid=4326)),
        sa.Column('speed_knots', sa.Float()),
        sa.Column('course_deg', sa.Float()),
        sa.Column('heading_deg', sa.Float()),
        sa.Column('navigation_status', sa.String(50)),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('source', sa.String(100)),
        sa.Column('is_real', sa.Boolean(), server_default='false'),
        sa.Column('data_mode', sa.String(10), server_default='demo'),
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_vessel_positions_location ON vessel_positions USING GIST (location)")

    # ── vessel_tracks ──────────────────────────────────────────────────────────
    op.create_table('vessel_tracks',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('vessel_name', sa.String(100)),
        sa.Column('mmsi', sa.String(20), index=True),
        sa.Column('track_geometry', geoalchemy2.types.Geometry('LINESTRING', srid=4326)),
        sa.Column('start_time', sa.DateTime(timezone=True)),
        sa.Column('end_time', sa.DateTime(timezone=True)),
        sa.Column('point_count', sa.Integer()),
        sa.Column('source', sa.String(100)),
        sa.Column('is_real', sa.Boolean(), server_default='false'),
    )

    # ── satellite_products ─────────────────────────────────────────────────────
    op.create_table('satellite_products',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('product_id', sa.String(200), unique=True, index=True),
        sa.Column('collection', sa.String(50), server_default='SENTINEL-1'),
        sa.Column('platform', sa.String(50)),
        sa.Column('instrument', sa.String(50)),
        sa.Column('product_type', sa.String(20)),
        sa.Column('polarization', sa.String(20)),
        sa.Column('orbit_direction', sa.String(20)),
        sa.Column('orbit_number', sa.Integer()),
        sa.Column('acquisition_time', sa.DateTime(timezone=True), index=True),
        sa.Column('publication_time', sa.DateTime(timezone=True)),
        sa.Column('footprint', geoalchemy2.types.Geometry('POLYGON', srid=4326)),
        sa.Column('thumbnail_url', sa.String(500)),
        sa.Column('download_url', sa.String(500)),
        sa.Column('source', sa.String(100)),
        sa.Column('processed', sa.Boolean(), server_default='false'),
        sa.Column('cloud_cover_pct', sa.Float()),
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_satellite_products_footprint ON satellite_products USING GIST (footprint)")

    # ── navigation_alerts ──────────────────────────────────────────────────────
    op.create_table('navigation_alerts',
        sa.Column('id', sa.String(8), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('alert_type', sa.String(50), nullable=False, index=True),
        sa.Column('level', sa.String(20), nullable=False),
        sa.Column('title', sa.String(200)),
        sa.Column('message', sa.String(1000)),
        sa.Column('data', sa.JSON()),
        sa.Column('acknowledged', sa.Boolean(), server_default='false'),
    )

    # ── data_source_status ─────────────────────────────────────────────────────
    op.create_table('data_source_status',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column('source_id', sa.String(50), unique=True, index=True),
        sa.Column('source_name', sa.String(100)),
        sa.Column('status', sa.String(30)),
        sa.Column('last_updated', sa.DateTime(timezone=True)),
        sa.Column('last_attempted', sa.DateTime(timezone=True)),
        sa.Column('last_error', sa.String(500)),
        sa.Column('record_count', sa.Integer()),
        sa.Column('error_count', sa.Integer(), server_default='0'),
        sa.Column('is_real', sa.Boolean(), server_default='false'),
        sa.Column('mode', sa.String(10)),
        sa.Column('source', sa.String(100)),
    )


def downgrade() -> None:
    op.drop_table('data_source_status')
    op.drop_table('navigation_alerts')
    op.drop_table('satellite_products')
    op.drop_table('vessel_tracks')
    op.drop_table('vessel_positions')
