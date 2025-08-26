"""
TrustCheck Database Models

SQLAlchemy models with change detection support.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Boolean, BigInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func, text
from datetime import datetime
from typing import List, Optional

Base = declarative_base()

# ======================== EXISTING MODELS (Enhanced) ========================

class SanctionedEntity(Base):
    """
    Stores sanctioned individuals and entities from various sources.
    Enhanced with change tracking support.
    """
    __tablename__ = "sanctioned_entities"
    
    # Primary identification
    id = Column(Integer, primary_key=True, index=True)
    uid = Column(String(100), unique=True, index=True)  # Source-specific ID
    name = Column(String(500), nullable=False, index=True)
    entity_type = Column(String(50))  # Person, Entity, Vessel, Aircraft
    
    # Source information
    source = Column(String(50), nullable=False, index=True)  # OFAC, UN, EU, etc.
    programs = Column(JSON)  # List of sanctions programs
    
    # Personal/Entity details
    aliases = Column(JSON)  # Alternative names/AKAs
    addresses = Column(JSON)  # List of addresses
    dates_of_birth = Column(JSON)  # List of birth dates
    places_of_birth = Column(JSON)  # List of birth places
    nationalities = Column(JSON)  # List of nationalities
    
    # Additional information
    remarks = Column(Text)  # Additional notes/remarks
    
    # Metadata (Enhanced for change detection)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_seen = Column(DateTime(timezone=True))  # Last time seen in source
    content_hash = Column(String(64))  # Hash of entity content for change detection
    
    def __repr__(self):
        return f"<SanctionedEntity(name='{self.name}', source='{self.source}')>"

# ======================== NEW CHANGE DETECTION MODELS ========================

class ContentSnapshot(Base):
    """
    Stores content snapshots for change detection and deduplication.
    """
    __tablename__ = "content_snapshots"
    
    # Primary identification
    snapshot_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    source = Column(String(50), nullable=False, index=True)
    
    # Content identification
    content_hash = Column(String(64), nullable=False, index=True)  # SHA-256 of raw content
    content_size_bytes = Column(BigInteger, nullable=False)
    
    # Timing information
    snapshot_time = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    scraper_run_id = Column(String(255), nullable=False, index=True)
    
    # Optional archive reference
    s3_archive_path = Column(String(500))  # S3 storage path for full content
    
    def __repr__(self):
        return f"<ContentSnapshot(source='{self.source}', hash='{self.content_hash[:12]}...')>"

class ChangeEvent(Base):
    """
    Records all detected changes in sanctioned entities.
    """
    __tablename__ = "change_events"
    
    # Primary identification
    event_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    
    # Entity identification
    entity_uid = Column(String(255), nullable=False, index=True)
    entity_name = Column(String(500), nullable=False)
    source = Column(String(50), nullable=False, index=True)
    
    # Change classification
    change_type = Column(String(20), nullable=False, index=True)  # ADDED, REMOVED, MODIFIED
    risk_level = Column(String(20), nullable=False, index=True)   # CRITICAL, HIGH, MEDIUM, LOW
    
    # Change details
    field_changes = Column(JSON, default=[])  # [{field, old_value, new_value}]
    change_summary = Column(Text, nullable=False)  # Human-readable description
    
    # Content verification
    old_content_hash = Column(String(64))
    new_content_hash = Column(String(64))
    
    # Timing and processing
    detected_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    scraper_run_id = Column(String(255), nullable=False)
    processing_time_ms = Column(Integer)
    
    # Notification tracking
    notification_sent_at = Column(DateTime(timezone=True))
    notification_channels = Column(JSON)  # ['email', 'webhook', 'slack']
    
    # Audit trail
    created_by = Column(String(100), default='system')
    
    def __repr__(self):
        return f"<ChangeEvent(entity='{self.entity_name}', type='{self.change_type}', risk='{self.risk_level}')>"

class ScraperRun(Base):
    """
    scraper run tracking with change detection metrics.
    """
    __tablename__ = "scraper_runs"
    
    # Primary identification
    run_id = Column(String(255), primary_key=True)  # source_timestamp format
    source = Column(String(50), nullable=False, index=True)
    
    # Execution timing
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True))
    duration_seconds = Column(Integer)
    status = Column(String(20), default='RUNNING', index=True)  # RUNNING, SUCCESS, FAILED, SKIPPED
    
    # Content analysis
    source_url = Column(String(500))
    content_hash = Column(String(64))
    content_size_bytes = Column(BigInteger)
    content_changed = Column(Boolean, default=False)
    
    # Entity processing results
    entities_processed = Column(Integer, default=0)
    entities_added = Column(Integer, default=0)
    entities_modified = Column(Integer, default=0)
    entities_removed = Column(Integer, default=0)
    
    # Change classification
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
    
    # Compliance tracking
    archived_to_s3 = Column(Boolean, default=False)
    s3_archive_path = Column(String(500))
    
    def __repr__(self):
        return f"<ScraperRun(run_id='{self.run_id}', status='{self.status}')>"

# ======================== LEGACY MODEL (Keep for compatibility) ========================

class EntityChangeLog(Base):
    """
    Legacy change log - keep for backward compatibility.
    New changes should use ChangeEvent instead.
    """
    __tablename__ = "entity_change_log"
    
    id = Column(Integer, primary_key=True, index=True)
    entity_uid = Column(String(100), index=True)
    change_type = Column(String(20))  # ADDED, MODIFIED, REMOVED
    field_changed = Column(String(100))  # Which field was changed
    old_value = Column(Text)
    new_value = Column(Text)
    source = Column(String(50))
    change_date = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<EntityChangeLog(entity_uid='{self.entity_uid}', change_type='{self.change_type}')>"

class ScrapingLog(Base):
    """
    Legacy scraping log - keep for backward compatibility.
    New runs should use ScraperRun instead.
    """
    __tablename__ = "scraping_log"
    
    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(50), nullable=False)
    status = Column(String(20))  # SUCCESS, FAILED, PARTIAL
    entities_processed = Column(Integer, default=0)
    entities_added = Column(Integer, default=0)
    entities_updated = Column(Integer, default=0)
    entities_removed = Column(Integer, default=0)
    error_message = Column(Text)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    duration_seconds = Column(Integer)
    
    def __repr__(self):
        return f"<ScrapingLog(source='{self.source}', status='{self.status}')>"