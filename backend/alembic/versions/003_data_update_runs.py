"""Add data_update_runs table for hourly orchestrator tracking

Revision ID: 003
Revises: 002
Create Date: 2024-01-03 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── data_update_runs ───────────────────────────────────────────────────────
    # One row per hourly update cycle
    op.create_table('data_update_runs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column('run_number', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True)),
        sa.Column('duration_seconds', sa.Float()),
        sa.Column('triggered_by', sa.String(30),
                  server_default='scheduler'),  # 'scheduler' | 'startup' | 'manual'
        sa.Column('overall_status', sa.String(20),
                  server_default='running'),     # 'running' | 'success' | 'partial' | 'failed'
        sa.Column('sources_attempted', sa.Integer(), server_default='0'),
        sa.Column('sources_succeeded', sa.Integer(), server_default='0'),
        sa.Column('sources_failed', sa.Integer(), server_default='0'),
        sa.Column('summary', sa.JSON()),          # {source: {status, records, error}}
        sa.Column('next_run_at', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_data_update_runs_started_at', 'data_update_runs', ['started_at'])

    # ── source_update_tasks ────────────────────────────────────────────────────
    # One row per source per run
    op.create_table('source_update_tasks',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column('run_id', UUID(as_uuid=True),
                  sa.ForeignKey('data_update_runs.id'), nullable=False),
        sa.Column('source_id', sa.String(50), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True)),
        sa.Column('status', sa.String(20), nullable=False),  # 'success'|'failed'|'skipped'|'no_new_data'
        sa.Column('records_received', sa.Integer(), server_default='0'),
        sa.Column('records_saved', sa.Integer(), server_default='0'),
        sa.Column('error_message', sa.String(1000)),
        sa.Column('observation_time', sa.DateTime(timezone=True)),  # newest obs time retrieved
        sa.Column('note', sa.String(500)),
    )
    op.create_index('ix_source_update_tasks_run_id', 'source_update_tasks', ['run_id'])
    op.create_index('ix_source_update_tasks_source_id', 'source_update_tasks', ['source_id'])

    # ── live_sea_ice_observations ──────────────────────────────────────────────
    # Real NSIDC observations stored persistently
    op.create_table('live_sea_ice_observations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('observation_date', sa.Date(), nullable=False, unique=True),
        sa.Column('extent_km2', sa.Float()),
        sa.Column('area_km2', sa.Float()),
        sa.Column('coverage_pct', sa.Float()),
        sa.Column('source', sa.String(100), server_default='NSIDC G02135 v3'),
        sa.Column('retrieved_at', sa.DateTime(timezone=True)),
        sa.Column('run_id', UUID(as_uuid=True), sa.ForeignKey('data_update_runs.id')),
    )
    op.create_index('ix_live_sea_ice_date', 'live_sea_ice_observations', ['observation_date'])

    # ── live_iceberg_observations ──────────────────────────────────────────────
    # Real NIC iceberg records stored persistently
    op.create_table('live_iceberg_observations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('retrieved_at', sa.DateTime(timezone=True)),
        sa.Column('iceberg_name', sa.String(50), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('length_km', sa.Float()),
        sa.Column('width_km', sa.Float()),
        sa.Column('area_km2', sa.Float()),
        sa.Column('observed_at', sa.DateTime(timezone=True)),
        sa.Column('source', sa.String(100), server_default='US National Ice Center'),
        sa.Column('source_url', sa.String(500)),
        sa.Column('run_id', UUID(as_uuid=True), sa.ForeignKey('data_update_runs.id')),
    )
    op.create_index('ix_live_iceberg_name', 'live_iceberg_observations', ['iceberg_name'])
    op.create_index('ix_live_iceberg_retrieved', 'live_iceberg_observations', ['retrieved_at'])

    # ── live_weather_observations ──────────────────────────────────────────────
    op.create_table('live_weather_observations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('retrieved_at', sa.DateTime(timezone=True)),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('wind_speed_ms', sa.Float()),
        sa.Column('wind_direction_deg', sa.Float()),
        sa.Column('air_temp_celsius', sa.Float()),
        sa.Column('sea_level_pressure_hpa', sa.Float()),
        sa.Column('precipitation_mm', sa.Float()),
        sa.Column('weather_code', sa.Integer()),
        sa.Column('source', sa.String(50), server_default='Open-Meteo'),
        sa.Column('run_id', UUID(as_uuid=True), sa.ForeignKey('data_update_runs.id')),
    )
    op.create_index('ix_live_weather_retrieved', 'live_weather_observations', ['retrieved_at'])

    # ── live_ocean_observations ────────────────────────────────────────────────
    op.create_table('live_ocean_observations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('retrieved_at', sa.DateTime(timezone=True)),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('current_speed_ms', sa.Float()),
        sa.Column('current_direction_deg', sa.Float()),
        sa.Column('current_u_ms', sa.Float()),
        sa.Column('current_v_ms', sa.Float()),
        sa.Column('significant_wave_height_m', sa.Float()),
        sa.Column('wave_period_s', sa.Float()),
        sa.Column('source', sa.String(50), server_default='Open-Meteo Marine'),
        sa.Column('run_id', UUID(as_uuid=True), sa.ForeignKey('data_update_runs.id')),
    )
    op.create_index('ix_live_ocean_retrieved', 'live_ocean_observations', ['retrieved_at'])

    # ── live_vessel_positions ──────────────────────────────────────────────────
    # Already have vessel_positions from migration 002 — add is_real check column
    try:
        op.add_column('vessel_positions',
            sa.Column('run_id', UUID(as_uuid=True), sa.ForeignKey('data_update_runs.id')))
    except Exception:
        pass  # Column may already exist


def downgrade() -> None:
    op.drop_table('live_ocean_observations')
    op.drop_table('live_weather_observations')
    op.drop_table('live_iceberg_observations')
    op.drop_table('live_sea_ice_observations')
    op.drop_table('source_update_tasks')
    op.drop_table('data_update_runs')
