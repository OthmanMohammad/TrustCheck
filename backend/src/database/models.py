"""
TrustCheck Database Models

SQLAlchemy models for storing sanctions data.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime
from typing import List, Optional

Base = declarative_base()

class SanctionedEntity(Base):
    """
    Stores sanctioned individuals and entities from various sources.
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
    
    # Metadata
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_seen = Column(DateTime(timezone=True))  # Last time seen in source
    
    def __repr__(self):
        return f"<SanctionedEntity(name='{self.name}', source='{self.source}')>"

class EntityChangeLog(Base):
    """
    Tracks changes to sanctioned entities for compliance audit trail.
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
    Logs scraping activities for monitoring and debugging.
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