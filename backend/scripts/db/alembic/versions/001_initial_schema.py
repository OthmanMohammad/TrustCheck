"""Initial schema

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create sanctioned_entities table
    op.create_table('sanctioned_entities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uid', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=500), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('programs', sa.JSON(), nullable=True),
        sa.Column('aliases', sa.JSON(), nullable=True),
        sa.Column('addresses', sa.JSON(), nullable=True),
        sa.Column('dates_of_birth', sa.JSON(), nullable=True),
        sa.Column('places_of_birth', sa.JSON(), nullable=True),
        sa.Column('nationalities', sa.JSON(), nullable=True),
        sa.Column('remarks', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_seen', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_entity_content_hash', 'sanctioned_entities', ['content_hash'], unique=False)
    op.create_index('idx_entity_source_active', 'sanctioned_entities', ['source', 'is_active'], unique=False)
    op.create_index('idx_entity_type_active', 'sanctioned_entities', ['entity_type', 'is_active'], unique=False)
    op.create_index('idx_entity_updated_at', 'sanctioned_entities', ['updated_at'], unique=False)
    op.create_index(op.f('ix_sanctioned_entities_entity_type'), 'sanctioned_entities', ['entity_type'], unique=False)
    op.create_index(op.f('ix_sanctioned_entities_id'), 'sanctioned_entities', ['id'], unique=False)
    op.create_index(op.f('ix_sanctioned_entities_is_active'), 'sanctioned_entities', ['is_active'], unique=False)
    op.create_index(op.f('ix_sanctioned_entities_last_seen'), 'sanctioned_entities', ['last_seen'], unique=False)
    op.create_index(op.f('ix_sanctioned_entities_name'), 'sanctioned_entities', ['name'], unique=False)
    op.create_index(op.f('ix_sanctioned_entities_source'), 'sanctioned_entities', ['source'], unique=False)
    op.create_index(op.f('ix_sanctioned_entities_uid'), 'sanctioned_entities', ['uid'], unique=True)

    # Create change_events table
    op.create_table('change_events',
        sa.Column('event_id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('entity_uid', sa.String(length=255), nullable=False),
        sa.Column('entity_name', sa.String(length=500), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('change_type', sa.String(length=20), nullable=False),
        sa.Column('risk_level', sa.String(length=20), nullable=False),
        sa.Column('field_changes', sa.JSON(), nullable=True),
        sa.Column('change_summary', sa.Text(), nullable=False),
        sa.Column('old_content_hash', sa.String(length=64), nullable=True),
        sa.Column('new_content_hash', sa.String(length=64), nullable=True),
        sa.Column('detected_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('scraper_run_id', sa.String(length=255), nullable=False),
        sa.Column('processing_time_ms', sa.Integer(), nullable=True),
        sa.Column('notification_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notification_channels', sa.JSON(), nullable=True),
        sa.Column('created_by', sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint('event_id')
    )
    op.create_index('idx_change_entity_time', 'change_events', ['entity_uid', 'detected_at'], unique=False)
    op.create_index('idx_change_notification_pending', 'change_events', ['notification_sent_at', 'risk_level'], unique=False)
    op.create_index('idx_change_risk_time', 'change_events', ['risk_level', 'detected_at'], unique=False)
    op.create_index('idx_change_scraper_run', 'change_events', ['scraper_run_id'], unique=False)
    op.create_index('idx_change_source_time', 'change_events', ['source', 'detected_at'], unique=False)
    op.create_index('idx_change_type_time', 'change_events', ['change_type', 'detected_at'], unique=False)

    # Create scraper_runs table
    op.create_table('scraper_runs',
        sa.Column('run_id', sa.String(length=255), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('source_url', sa.String(length=500), nullable=True),
        sa.Column('content_hash', sa.String(length=64), nullable=True),
        sa.Column('content_size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('content_changed', sa.Boolean(), nullable=True),
        sa.Column('entities_processed', sa.Integer(), nullable=True),
        sa.Column('entities_added', sa.Integer(), nullable=True),
        sa.Column('entities_modified', sa.Integer(), nullable=True),
        sa.Column('entities_removed', sa.Integer(), nullable=True),
        sa.Column('critical_changes', sa.Integer(), nullable=True),
        sa.Column('high_risk_changes', sa.Integer(), nullable=True),
        sa.Column('medium_risk_changes', sa.Integer(), nullable=True),
        sa.Column('low_risk_changes', sa.Integer(), nullable=True),
        sa.Column('download_time_ms', sa.Integer(), nullable=True),
        sa.Column('parsing_time_ms', sa.Integer(), nullable=True),
        sa.Column('diff_time_ms', sa.Integer(), nullable=True),
        sa.Column('storage_time_ms', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True),
        sa.Column('archived_to_s3', sa.Boolean(), nullable=True),
        sa.Column('s3_archive_path', sa.String(length=500), nullable=True),
        sa.Column('celery_task_id', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('run_id')
    )
    op.create_index('idx_scraper_content_changed', 'scraper_runs', ['content_changed', 'started_at'], unique=False)
    op.create_index('idx_scraper_source_time', 'scraper_runs', ['source', 'started_at'], unique=False)
    op.create_index('idx_scraper_status_time', 'scraper_runs', ['status', 'started_at'], unique=False)
    op.create_index('idx_scraper_success_source', 'scraper_runs', ['status', 'source', 'started_at'], unique=False)

    # Create content_snapshots table
    op.create_table('content_snapshots',
        sa.Column('snapshot_id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('content_size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('snapshot_time', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('scraper_run_id', sa.String(length=255), nullable=False),
        sa.Column('s3_archive_path', sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint('snapshot_id')
    )
    op.create_index('idx_snapshot_hash_source', 'content_snapshots', ['content_hash', 'source'], unique=False)
    op.create_index('idx_snapshot_run_id', 'content_snapshots', ['scraper_run_id'], unique=False)
    op.create_index('idx_snapshot_source_time', 'content_snapshots', ['source', 'snapshot_time'], unique=False)

    # Create legacy tables for backward compatibility
    op.create_table('entity_change_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('entity_uid', sa.String(length=100), nullable=True),
        sa.Column('change_type', sa.String(length=20), nullable=True),
        sa.Column('field_changed', sa.String(length=100), nullable=True),
        sa.Column('old_value', sa.Text(), nullable=True),
        sa.Column('new_value', sa.Text(), nullable=True),
        sa.Column('source', sa.String(length=50), nullable=True),
        sa.Column('change_date', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_legacy_entity_change', 'entity_change_log', ['entity_uid', 'change_date'], unique=False)

    op.create_table('scraping_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('entities_processed', sa.Integer(), nullable=True),
        sa.Column('entities_added', sa.Integer(), nullable=True),
        sa.Column('entities_updated', sa.Integer(), nullable=True),
        sa.Column('entities_removed', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_legacy_scraping_log', 'scraping_log', ['source', 'completed_at'], unique=False)


def downgrade() -> None:
    op.drop_table('scraping_log')
    op.drop_table('entity_change_log')
    op.drop_table('content_snapshots')
    op.drop_table('scraper_runs')
    op.drop_table('change_events')
    op.drop_table('sanctioned_entities')