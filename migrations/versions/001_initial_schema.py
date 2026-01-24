"""Initial database schema.

Revision ID: 001
Revises:
Create Date: 2026-01-24

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create entities table
    op.create_table(
        "entities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("primary_name", sa.String(500), nullable=False),
        sa.Column("primary_name_normalized", sa.String(500), nullable=False),
        sa.Column("date_of_birth", sa.String(20), nullable=True),
        sa.Column("year_of_birth", sa.Integer, nullable=True),
        sa.Column("place_of_birth", sa.String(255), nullable=True),
        sa.Column("nationality", sa.String(10), nullable=True),
        sa.Column("remarks", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("idx_entity_type", "entities", ["entity_type"])
    op.create_index("idx_entity_active", "entities", ["is_active"])
    op.create_index("idx_entity_active_type", "entities", ["is_active", "entity_type"])
    op.create_index("idx_entity_name_normalized", "entities", ["primary_name_normalized"])

    # Create names table
    op.create_table(
        "names",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("entity_id", sa.String(36), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name_type", sa.String(50), nullable=False),
        sa.Column("name_value", sa.String(500), nullable=False),
        sa.Column("name_normalized", sa.String(500), nullable=False),
        sa.Column("script", sa.String(20), default="LATIN"),
    )
    op.create_index("idx_name_entity", "names", ["entity_id"])
    op.create_index("idx_name_normalized", "names", ["name_normalized"])
    op.create_index("idx_name_entity_type", "names", ["entity_id", "name_type"])

    # Create addresses table
    op.create_table(
        "addresses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("entity_id", sa.String(36), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("country", sa.String(10), nullable=True),
        sa.Column("city", sa.String(255), nullable=True),
        sa.Column("street", sa.String(500), nullable=True),
        sa.Column("postal_code", sa.String(50), nullable=True),
        sa.Column("full_address", sa.Text, nullable=True),
    )
    op.create_index("idx_address_entity", "addresses", ["entity_id"])

    # Create identifiers table
    op.create_table(
        "identifiers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("entity_id", sa.String(36), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("id_type", sa.String(50), nullable=False),
        sa.Column("id_value", sa.String(255), nullable=False),
        sa.Column("country", sa.String(10), nullable=True),
        sa.Column("issue_date", sa.String(20), nullable=True),
        sa.Column("expiry_date", sa.String(20), nullable=True),
    )
    op.create_index("idx_identifier_entity", "identifiers", ["entity_id"])
    op.create_index("idx_identifier_type_value", "identifiers", ["id_type", "id_value"])

    # Create source_records table
    op.create_table(
        "source_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("entity_id", sa.String(36), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("source_uid", sa.String(255), nullable=False),
        sa.Column("programs", sa.Text, nullable=True),
        sa.Column("raw_data", sa.Text, nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("first_seen_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("idx_source_record_entity", "source_records", ["entity_id"])
    op.create_index("idx_source_record_source", "source_records", ["source"])
    op.create_index("idx_source_record_source_uid", "source_records", ["source", "source_uid"], unique=True)
    op.create_index("idx_source_record_hash", "source_records", ["content_hash"])

    # Create events table (audit log)
    op.create_table(
        "events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("aggregate_type", sa.String(50), default="ENTITY"),
        sa.Column("aggregate_id", sa.String(36), nullable=False),
        sa.Column("event_data", sa.Text, nullable=False),
        sa.Column("event_metadata", sa.Text, nullable=True),
        sa.Column("occurred_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("idx_event_type", "events", ["event_type"])
    op.create_index("idx_event_aggregate_id", "events", ["aggregate_id"])
    op.create_index("idx_event_aggregate", "events", ["aggregate_type", "aggregate_id"])
    op.create_index("idx_event_occurred", "events", ["occurred_at"])
    op.create_index("idx_event_type_time", "events", ["event_type", "occurred_at"])

    # Create scraper_runs table
    op.create_table(
        "scraper_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, default="RUNNING"),
        sa.Column("started_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("entities_processed", sa.Integer, default=0),
        sa.Column("entities_added", sa.Integer, default=0),
        sa.Column("entities_modified", sa.Integer, default=0),
        sa.Column("entities_removed", sa.Integer, default=0),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
    )
    op.create_index("idx_scraper_run_source", "scraper_runs", ["source"])
    op.create_index("idx_scraper_run_status", "scraper_runs", ["status"])
    op.create_index("idx_scraper_run_source_time", "scraper_runs", ["source", "started_at"])

    # Create change_events table
    op.create_table(
        "change_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("entity_name", sa.String(500), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("change_type", sa.String(20), nullable=False),
        sa.Column("field_changes", sa.Text, nullable=True),
        sa.Column("old_values", sa.Text, nullable=True),
        sa.Column("new_values", sa.Text, nullable=True),
        sa.Column("detected_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("scraper_run_id", sa.String(36), nullable=True),
    )
    op.create_index("idx_change_entity", "change_events", ["entity_id"])
    op.create_index("idx_change_source", "change_events", ["source"])
    op.create_index("idx_change_type", "change_events", ["change_type"])
    op.create_index("idx_change_detected", "change_events", ["detected_at"])
    op.create_index("idx_change_source_time", "change_events", ["source", "detected_at"])
    op.create_index("idx_change_type_time", "change_events", ["change_type", "detected_at"])

    # Create screening_results table
    op.create_table(
        "screening_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("query_name", sa.String(500), nullable=False),
        sa.Column("query_normalized", sa.String(500), nullable=False),
        sa.Column("matched_entity_id", sa.String(36), nullable=True),
        sa.Column("match_score", sa.Float, nullable=False),
        sa.Column("match_type", sa.String(50), nullable=False),
        sa.Column("matched_fields", sa.Text, nullable=True),
        sa.Column("screened_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("processing_time_ms", sa.Float, default=0.0),
    )
    op.create_index("idx_screening_request", "screening_results", ["request_id"])
    op.create_index("idx_screening_time", "screening_results", ["screened_at"])


def downgrade() -> None:
    op.drop_table("screening_results")
    op.drop_table("change_events")
    op.drop_table("scraper_runs")
    op.drop_table("events")
    op.drop_table("source_records")
    op.drop_table("identifiers")
    op.drop_table("addresses")
    op.drop_table("names")
    op.drop_table("entities")
