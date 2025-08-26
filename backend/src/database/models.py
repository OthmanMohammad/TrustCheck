"""
Clean Database Models - Pure SQLAlchemy ORM

These models contain ONLY:
- Table definitions
- Column mappings  
- Relationships
- Database constraints

NO business logic.
Domain logic belongs in domain entities and services.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Boolean, BigInteger, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func, text
from typing import Optional

Base = declarative_base()

# ======================== CORE ENTITY TABLES ========================

class SanctionedEntity(Base):
    """
    Pure ORM model for sanctioned entities.
    
    Maps directly to database table structure.
    Contains no business logic or domain methods.
    """
    __tablename__ = "sanctioned_entities"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Core identification
    uid = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(500), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False, index=True)
    source = Column(String(50), nullable=False, index=True)
    
    # Sanctions data (stored as JSON)
    programs = Column(JSON, default=list)
    aliases = Column(JSON, default=list)
    addresses = Column(JSON, default=list)
    dates_of_birth = Column(JSON, default=list)
    places_of_birth = Column(JSON, default=list)
    nationalities = Column(JSON, default=list)
    
    # Additional information
    remarks = Column(Text)
    
    # Status and metadata
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    content_hash = Column(String(64), index=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_seen = Column(DateTime(timezone=True), index=True)
    
    # Database indexes for performance
    __table_args__ = (
        Index('idx_entity_source_active', 'source', 'is_active'),
        Index('idx_entity_type_active', 'entity_type', 'is_active'),
        Index('idx_entity_updated_at', 'updated_at'),
        Index('idx_entity_content_hash', 'content_hash'),
        # PostgreSQL-specific indexes for JSON fields
        Index('idx_entity_programs_gin', 'programs', postgresql_using='gin'),
        Index('idx_entity_aliases_gin', 'aliases', postgresql_using='gin'),
    )

class ChangeEvent(Base):
    """
    Pure ORM model for change events.
    
    Records detected changes in sanctioned entities.
    """
    __tablename__ = "change_events"
    
    # Primary key
    event_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    
    # Entity identification
    entity_uid = Column(String(255), nullable=False, index=True)
    entity_name = Column(String(500), nullable=False)
    source = Column(String(50), nullable=False, index=True)
    
    # Change classification
    change_type = Column(String(20), nullable=False, index=True)  # ADDED, REMOVED, MODIFIED
    risk_level = Column(String(20), nullable=False, index=True)   # CRITICAL, HIGH, MEDIUM, LOW
    
    # Change details
    field_changes = Column(JSON, default=list)
    change_summary = Column(Text, nullable=False)
    
    # Content verification
    old_content_hash = Column(String(64))
    new_content_hash = Column(String(64))
    
    # Timing and processing
    detected_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    scraper_run_id = Column(String(255), nullable=False, index=True)
    processing_time_ms = Column(Integer)
    
    # Notification tracking
    notification_sent_at = Column(DateTime(timezone=True))
    notification_channels = Column(JSON, default=list)
    
    # Audit
    created_by = Column(String(100), default='system')
    
    # Database indexes
    __table_args__ = (
        Index('idx_change_source_time', 'source', 'detected_at'),
        Index('idx_change_risk_time', 'risk_level', 'detected_at'),
        Index('idx_change_type_time', 'change_type', 'detected_at'),
        Index('idx_change_entity_time', 'entity_uid', 'detected_at'),
        Index('idx_change_scraper_run', 'scraper_run_id'),
        Index('idx_change_notification_pending', 'notification_sent_at', 'risk_level'),
    )

class ScraperRun(Base):
    """
    Pure ORM model for scraper execution tracking.
    
    Records metadata about each scraper execution.
    """
    __tablename__ = "scraper_runs"
    
    # Primary key
    run_id = Column(String(255), primary_key=True)
    source = Column(String(50), nullable=False, index=True)
    
    # Execution timing
    started_at = Column(DateTime(timezone=True), nullable=False, index=True)
    completed_at = Column(DateTime(timezone=True))
    duration_seconds = Column(Integer)
    status = Column(String(20), default='RUNNING', nullable=False, index=True)
    
    # Source and content analysis
    source_url = Column(String(500))
    content_hash = Column(String(64))
    content_size_bytes = Column(BigInteger)
    content_changed = Column(Boolean, default=False)
    
    # Entity processing results
    entities_processed = Column(Integer, default=0)
    entities_added = Column(Integer, default=0)
    entities_modified = Column(Integer, default=0)
    entities_removed = Column(Integer, default=0)
    
    # Change classification counts
    critical_changes = Column(Integer, default=0)
    high_risk_changes = Column(Integer, default=0)
    medium_risk_changes = Column(Integer, default=0)
    low_risk_changes = Column(Integer, default=0)
    
    # Performance metrics
    download_time_ms = Column(Integer)
    parsing_time_ms = Column(Integer)
    diff_time_ms = Column(Integer)
    storage_time_ms = Column(Integer)
    
    # Error handling
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    
    # Archive tracking
    archived_to_s3 = Column(Boolean, default=False)
    s3_archive_path = Column(String(500))
    
    # Database indexes
    __table_args__ = (
        Index('idx_scraper_source_time', 'source', 'started_at'),
        Index('idx_scraper_status_time', 'status', 'started_at'),
        Index('idx_scraper_content_changed', 'content_changed', 'started_at'),
        Index('idx_scraper_success_source', 'status', 'source', 'started_at'),
    )

class ContentSnapshot(Base):
    """
    Pure ORM model for content snapshots.
    
    Stores content fingerprints for change detection.
    """
    __tablename__ = "content_snapshots"
    
    # Primary key
    snapshot_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    source = Column(String(50), nullable=False, index=True)
    
    # Content identification
    content_hash = Column(String(64), nullable=False, index=True)
    content_size_bytes = Column(BigInteger, nullable=False)
    
    # Timing
    snapshot_time = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    scraper_run_id = Column(String(255), nullable=False, index=True)
    
    # Archive reference
    s3_archive_path = Column(String(500))
    
    # Database indexes
    __table_args__ = (
        Index('idx_snapshot_source_time', 'source', 'snapshot_time'),
        Index('idx_snapshot_hash_source', 'content_hash', 'source'),
        Index('idx_snapshot_run_id', 'scraper_run_id'),
    )

# ======================== LEGACY TABLES (For Backward Compatibility) ========================

class EntityChangeLog(Base):
    """
    Legacy change log table.
    
    Kept for backward compatibility with existing code.
    New code should use ChangeEvent instead.
    """
    __tablename__ = "entity_change_log"
    
    id = Column(Integer, primary_key=True, index=True)
    entity_uid = Column(String(100), index=True)
    change_type = Column(String(20))
    field_changed = Column(String(100))
    old_value = Column(Text)
    new_value = Column(Text)
    source = Column(String(50))
    change_date = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        Index('idx_legacy_entity_change', 'entity_uid', 'change_date'),
    )

class ScrapingLog(Base):
    """
    Legacy scraping log table.
    
    Kept for backward compatibility with existing code.
    New code should use ScraperRun instead.
    """
    __tablename__ = "scraping_log"
    
    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(50), nullable=False)
    status = Column(String(20))
    entities_processed = Column(Integer, default=0)
    entities_added = Column(Integer, default=0)
    entities_updated = Column(Integer, default=0)
    entities_removed = Column(Integer, default=0)
    error_message = Column(Text)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    duration_seconds = Column(Integer)
    
    __table_args__ = (
        Index('idx_legacy_scraping_log', 'source', 'completed_at'),
    )

# ======================== DATABASE VIEWS (Optional) ========================

class EntitySummaryView(Base):
    """
    Database view for entity summary statistics.
    
    This would be created as a materialized view in PostgreSQL
    for fast dashboard queries.
    """
    __tablename__ = "entity_summary_view"
    
    # This is a view, not a real table
    __table_args__ = {'info': {'is_view': True}}
    
    id = Column(Integer, primary_key=True)
    source = Column(String(50))
    entity_type = Column(String(50))
    total_count = Column(Integer)
    active_count = Column(Integer)
    last_updated = Column(DateTime(timezone=True))

class ChangesSummaryView(Base):
    """
    Database view for change summary statistics.
    
    Materialized view for dashboard performance.
    """
    __tablename__ = "changes_summary_view"
    
    __table_args__ = {'info': {'is_view': True}}
    
    id = Column(Integer, primary_key=True)
    date = Column(DateTime(timezone=True))
    source = Column(String(50))
    risk_level = Column(String(20))
    change_type = Column(String(20))
    count = Column(Integer)

# ======================== DATABASE FUNCTIONS AND TRIGGERS ========================

# SQL for creating PostgreSQL-specific functions and triggers
# This would be executed through Alembic migrations

CREATE_FUNCTIONS_SQL = """
-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Function to calculate content hash change
CREATE OR REPLACE FUNCTION detect_content_change()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.content_hash != NEW.content_hash THEN
        -- Content changed, could trigger notifications
        PERFORM pg_notify('content_changed', 
            json_build_object(
                'source', NEW.source,
                'old_hash', OLD.content_hash,
                'new_hash', NEW.content_hash
            )::text
        );
    END IF;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Function for fuzzy name matching
CREATE OR REPLACE FUNCTION fuzzy_match_entity_name(search_name TEXT, threshold FLOAT DEFAULT 0.3)
RETURNS TABLE(
    id INTEGER,
    name TEXT,
    similarity_score FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        e.id,
        e.name,
        similarity(e.name, search_name) as similarity_score
    FROM sanctioned_entities e
    WHERE similarity(e.name, search_name) > threshold
    ORDER BY similarity_score DESC
    LIMIT 100;
END;
$$ language 'plpgsql';
"""

CREATE_TRIGGERS_SQL = """
-- Trigger to update updated_at on sanctioned_entities
DROP TRIGGER IF EXISTS update_sanctioned_entities_updated_at ON sanctioned_entities;
CREATE TRIGGER update_sanctioned_entities_updated_at
    BEFORE UPDATE ON sanctioned_entities
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger to detect content changes
DROP TRIGGER IF EXISTS detect_content_change_trigger ON sanctioned_entities;
CREATE TRIGGER detect_content_change_trigger
    AFTER UPDATE OF content_hash ON sanctioned_entities
    FOR EACH ROW
    WHEN (OLD.content_hash IS DISTINCT FROM NEW.content_hash)
    EXECUTE FUNCTION detect_content_change();
"""

CREATE_VIEWS_SQL = """
-- Materialized view for entity summaries
DROP MATERIALIZED VIEW IF EXISTS entity_summary_view CASCADE;
CREATE MATERIALIZED VIEW entity_summary_view AS
SELECT 
    ROW_NUMBER() OVER() as id,
    source,
    entity_type,
    COUNT(*) as total_count,
    COUNT(*) FILTER (WHERE is_active = true) as active_count,
    MAX(updated_at) as last_updated
FROM sanctioned_entities
GROUP BY source, entity_type;

-- Index on materialized view
CREATE INDEX idx_entity_summary_source ON entity_summary_view(source);

-- Materialized view for changes summary
DROP MATERIALIZED VIEW IF EXISTS changes_summary_view CASCADE;
CREATE MATERIALIZED VIEW changes_summary_view AS
SELECT 
    ROW_NUMBER() OVER() as id,
    DATE_TRUNC('day', detected_at) as date,
    source,
    risk_level,
    change_type,
    COUNT(*) as count
FROM change_events
WHERE detected_at >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY DATE_TRUNC('day', detected_at), source, risk_level, change_type
ORDER BY date DESC;

-- Index on changes summary view
CREATE INDEX idx_changes_summary_date ON changes_summary_view(date);
CREATE INDEX idx_changes_summary_source ON changes_summary_view(source);
"""

REFRESH_VIEWS_SQL = """
-- Function to refresh materialized views
CREATE OR REPLACE FUNCTION refresh_summary_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY entity_summary_view;
    REFRESH MATERIALIZED VIEW CONCURRENTLY changes_summary_view;
END;
$$ language 'plpgsql';
"""

# ======================== TABLE COMMENTS FOR DOCUMENTATION ========================

TABLE_COMMENTS_SQL = """
-- Add table comments for documentation
COMMENT ON TABLE sanctioned_entities IS 'Core table storing sanctioned individuals and organizations from various sources';
COMMENT ON TABLE change_events IS 'Records all detected changes in sanctioned entity data with risk classification';
COMMENT ON TABLE scraper_runs IS 'Tracks execution of scrapers with performance metrics and change detection results';
COMMENT ON TABLE content_snapshots IS 'Stores content fingerprints for change detection and audit trail';

-- Add column comments
COMMENT ON COLUMN sanctioned_entities.uid IS 'Unique identifier from source system';
COMMENT ON COLUMN sanctioned_entities.content_hash IS 'SHA-256 hash of entity content for change detection';
COMMENT ON COLUMN change_events.risk_level IS 'Business risk level: CRITICAL, HIGH, MEDIUM, LOW';
COMMENT ON COLUMN change_events.field_changes IS 'JSON array of specific field changes';
COMMENT ON COLUMN scraper_runs.status IS 'Execution status: RUNNING, SUCCESS, FAILED, SKIPPED';
COMMENT ON COLUMN content_snapshots.content_hash IS 'SHA-256 hash of raw source content';
"""

# ======================== EXPORTS ========================

__all__ = [
    # Database base
    'Base',
    
    # Core tables
    'SanctionedEntity',
    'ChangeEvent',
    'ScraperRun',
    'ContentSnapshot',
    
    # Legacy tables
    'EntityChangeLog',
    'ScrapingLog',
    
    # Views
    'EntitySummaryView',
    'ChangesSummaryView',
    
    # SQL constants for migrations
    'CREATE_FUNCTIONS_SQL',
    'CREATE_TRIGGERS_SQL',
    'CREATE_VIEWS_SQL',
    'REFRESH_VIEWS_SQL',
    'TABLE_COMMENTS_SQL'
]