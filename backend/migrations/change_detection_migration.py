"""
Change Detection Migration Script

Production-grade migration with:
- Rollback support
- Data preservation
- Performance optimizations
- Error handling
"""

import logging
from typing import List, Dict, Any
from sqlalchemy import text, MetaData, Table, Column, inspect
from datetime import datetime

from src.infrastructure.database.connection import db_manager
from src.core.exceptions import DatabaseError, DatabaseOperationError
from src.utils.logging import get_logger

# ======================== MIGRATION METADATA ========================

MIGRATION_ID = "20240101_001"
MIGRATION_NAME = "add_change_detection_tables"
MIGRATION_DESCRIPTION = """
Add change detection capabilities to TrustCheck:
- content_snapshots table for audit trail
- change_events table for tracking changes
- scraper_runs table for execution history
- Add content_hash column to sanctioned_entities
"""

logger = get_logger("migration.change_detection")

# ======================== MIGRATION CLASS ========================

class ChangeDetectionMigration:
    """
    Change detection migration with comprehensive error handling.
    """
    
    def __init__(self):
        self.metadata = MetaData()
        self.migration_id = MIGRATION_ID
        self.migration_name = MIGRATION_NAME
        
    # ======================== MAIN MIGRATION METHODS ========================
    
    def upgrade(self) -> None:
        """Apply the migration."""
        logger.info(f"Starting migration {self.migration_id}: {self.migration_name}")
        
        try:
            with db_manager.get_session() as db:
                # Check if migration already applied
                if self._is_migration_applied(db):
                    logger.info("Migration already applied, skipping")
                    return
                
                # Step 1: Add content_hash column to existing table
                self._add_content_hash_column(db)
                
                # Step 2: Create new change detection tables
                self._create_change_detection_tables(db)
                
                # Step 3: Create indexes for performance
                self._create_indexes(db)
                
                # Step 4: Create triggers if needed
                self._create_triggers(db)
                
                # Step 5: Record migration
                self._record_migration(db)
                
                db.commit()
                
            logger.info(f"Migration {self.migration_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Migration {self.migration_id} failed: {e}")
            raise DatabaseOperationError(f"Migration failed: {str(e)}")
    
    def downgrade(self) -> None:
        """Rollback the migration."""
        logger.info(f"Rolling back migration {self.migration_id}")
        
        try:
            with db_manager.get_session() as db:
                # Check if migration was applied
                if not self._is_migration_applied(db):
                    logger.info("Migration not applied, nothing to rollback")
                    return
                
                # Step 1: Drop triggers
                self._drop_triggers(db)
                
                # Step 2: Drop indexes
                self._drop_indexes(db)
                
                # Step 3: Drop change detection tables
                self._drop_change_detection_tables(db)
                
                # Step 4: Remove content_hash column
                self._remove_content_hash_column(db)
                
                # Step 5: Remove migration record
                self._remove_migration_record(db)
                
                db.commit()
                
            logger.info(f"Migration {self.migration_id} rolled back successfully")
            
        except Exception as e:
            logger.error(f"Migration rollback {self.migration_id} failed: {e}")
            raise DatabaseOperationError(f"Migration rollback failed: {str(e)}")
    
    # ======================== MIGRATION STEPS ========================
    
    def _add_content_hash_column(self, db) -> None:
        """Add content_hash column to sanctioned_entities."""
        logger.info("Adding content_hash column to sanctioned_entities")
        
        # Check if column already exists
        inspector = inspect(db.bind)
        columns = inspector.get_columns('sanctioned_entities')
        column_names = [col['name'] for col in columns]
        
        if 'content_hash' in column_names:
            logger.info("content_hash column already exists")
            return
        
        # Add column with default value
        db.execute(text("""
            ALTER TABLE sanctioned_entities 
            ADD COLUMN content_hash VARCHAR(64) DEFAULT NULL
        """))
        
        # Add comment
        db.execute(text("""
            COMMENT ON COLUMN sanctioned_entities.content_hash 
            IS 'SHA-256 hash of entity content for change detection'
        """))
        
        logger.info("content_hash column added successfully")
    
    def _create_change_detection_tables(self, db) -> None:
        """Create change detection tables."""
        logger.info("Creating change detection tables")
        
        # Create content_snapshots table
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS content_snapshots (
                snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                source VARCHAR(50) NOT NULL,
                content_hash VARCHAR(64) NOT NULL,
                content_size_bytes BIGINT NOT NULL,
                snapshot_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                scraper_run_id VARCHAR(255) NOT NULL,
                s3_archive_path VARCHAR(500),
                
                CONSTRAINT content_snapshots_source_check 
                    CHECK (source IN ('US_OFAC', 'UN_CONSOLIDATED', 'EU_CONSOLIDATED', 'UK_HMT'))
            )
        """))
        
        # Create change_events table  
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS change_events (
                event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                entity_uid VARCHAR(255) NOT NULL,
                entity_name VARCHAR(500) NOT NULL,
                source VARCHAR(50) NOT NULL,
                change_type VARCHAR(20) NOT NULL,
                risk_level VARCHAR(20) NOT NULL,
                field_changes JSONB DEFAULT '[]'::jsonb,
                change_summary TEXT NOT NULL,
                old_content_hash VARCHAR(64),
                new_content_hash VARCHAR(64),
                detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                scraper_run_id VARCHAR(255) NOT NULL,
                processing_time_ms INTEGER,
                notification_sent_at TIMESTAMPTZ,
                notification_channels JSONB,
                created_by VARCHAR(100) DEFAULT 'system',
                
                CONSTRAINT change_events_type_check 
                    CHECK (change_type IN ('ADDED', 'MODIFIED', 'REMOVED')),
                CONSTRAINT change_events_risk_check 
                    CHECK (risk_level IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')),
                CONSTRAINT change_events_source_check 
                    CHECK (source IN ('US_OFAC', 'UN_CONSOLIDATED', 'EU_CONSOLIDATED', 'UK_HMT'))
            )
        """))
        
        # Create scraper_runs table
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS scraper_runs (
                run_id VARCHAR(255) PRIMARY KEY,
                source VARCHAR(50) NOT NULL,
                started_at TIMESTAMPTZ NOT NULL,
                completed_at TIMESTAMPTZ,
                duration_seconds INTEGER,
                status VARCHAR(20) DEFAULT 'RUNNING',
                source_url VARCHAR(500),
                content_hash VARCHAR(64),
                content_size_bytes BIGINT,
                content_changed BOOLEAN DEFAULT FALSE,
                entities_processed INTEGER DEFAULT 0,
                entities_added INTEGER DEFAULT 0,
                entities_modified INTEGER DEFAULT 0,
                entities_removed INTEGER DEFAULT 0,
                critical_changes INTEGER DEFAULT 0,
                high_risk_changes INTEGER DEFAULT 0,
                medium_risk_changes INTEGER DEFAULT 0,
                low_risk_changes INTEGER DEFAULT 0,
                download_time_ms INTEGER,
                parsing_time_ms INTEGER,
                diff_time_ms INTEGER,
                storage_time_ms INTEGER,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                archived_to_s3 BOOLEAN DEFAULT FALSE,
                s3_archive_path VARCHAR(500),
                
                CONSTRAINT scraper_runs_status_check 
                    CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED', 'SKIPPED', 'PARTIAL')),
                CONSTRAINT scraper_runs_source_check 
                    CHECK (source IN ('us_ofac', 'un_consolidated', 'eu_consolidated', 'uk_hmt'))
            )
        """))
        
        logger.info("Change detection tables created successfully")
    
    def _create_indexes(self, db) -> None:
        """Create performance indexes."""
        logger.info("Creating performance indexes")
        
        indexes = [
            # content_snapshots indexes
            "CREATE INDEX IF NOT EXISTS idx_content_snapshots_source_time ON content_snapshots(source, snapshot_time DESC)",
            "CREATE INDEX IF NOT EXISTS idx_content_snapshots_hash ON content_snapshots(content_hash)",
            "CREATE INDEX IF NOT EXISTS idx_content_snapshots_run_id ON content_snapshots(scraper_run_id)",
            
            # change_events indexes
            "CREATE INDEX IF NOT EXISTS idx_change_events_detected_time ON change_events(detected_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_change_events_risk_time ON change_events(risk_level, detected_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_change_events_source_type ON change_events(source, change_type, detected_at)",
            "CREATE INDEX IF NOT EXISTS idx_change_events_entity_uid ON change_events(entity_uid)",
            "CREATE INDEX IF NOT EXISTS idx_change_events_run_id ON change_events(scraper_run_id)",
            
            # scraper_runs indexes
            "CREATE INDEX IF NOT EXISTS idx_scraper_runs_source_time ON scraper_runs(source, started_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_scraper_runs_status_time ON scraper_runs(status, started_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_scraper_runs_content_hash ON scraper_runs(content_hash)",
            
            # sanctioned_entities indexes
            "CREATE INDEX IF NOT EXISTS idx_sanctioned_entities_content_hash ON sanctioned_entities(content_hash)",
            "CREATE INDEX IF NOT EXISTS idx_sanctioned_entities_source_active ON sanctioned_entities(source, is_active)",
        ]
        
        for index_sql in indexes:
            db.execute(text(index_sql))
        
        logger.info(f"Created {len(indexes)} performance indexes")
    
    def _create_triggers(self, db) -> None:
        """Create database triggers if needed."""
        logger.info("Creating database triggers")
        
        # Trigger to update updated_at timestamp
        db.execute(text("""
            CREATE OR REPLACE FUNCTION update_updated_at_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = NOW();
                RETURN NEW;
            END;
            $$ language 'plpgsql';
        """))
        
        # Apply trigger to sanctioned_entities if updated_at exists
        db.execute(text("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'sanctioned_entities' 
                    AND column_name = 'updated_at'
                ) THEN
                    DROP TRIGGER IF EXISTS trigger_sanctioned_entities_updated_at ON sanctioned_entities;
                    CREATE TRIGGER trigger_sanctioned_entities_updated_at
                        BEFORE UPDATE ON sanctioned_entities
                        FOR EACH ROW
                        EXECUTE FUNCTION update_updated_at_column();
                END IF;
            END
            $$;
        """))
        
        logger.info("Database triggers created")
    
    # ======================== ROLLBACK METHODS ========================
    
    def _drop_triggers(self, db) -> None:
        """Drop database triggers."""
        logger.info("Dropping database triggers")
        
        db.execute(text("""
            DROP TRIGGER IF EXISTS trigger_sanctioned_entities_updated_at ON sanctioned_entities;
            DROP FUNCTION IF EXISTS update_updated_at_column();
        """))
        
        logger.info("Database triggers dropped")
    
    def _drop_indexes(self, db) -> None:
        """Drop performance indexes."""
        logger.info("Dropping performance indexes")
        
        indexes = [
            "DROP INDEX IF EXISTS idx_content_snapshots_source_time",
            "DROP INDEX IF EXISTS idx_content_snapshots_hash", 
            "DROP INDEX IF EXISTS idx_content_snapshots_run_id",
            "DROP INDEX IF EXISTS idx_change_events_detected_time",
            "DROP INDEX IF EXISTS idx_change_events_risk_time",
            "DROP INDEX IF EXISTS idx_change_events_source_type",
            "DROP INDEX IF EXISTS idx_change_events_entity_uid",
            "DROP INDEX IF EXISTS idx_change_events_run_id",
            "DROP INDEX IF EXISTS idx_scraper_runs_source_time",
            "DROP INDEX IF EXISTS idx_scraper_runs_status_time",
            "DROP INDEX IF EXISTS idx_scraper_runs_content_hash",
            "DROP INDEX IF EXISTS idx_sanctioned_entities_content_hash",
            "DROP INDEX IF EXISTS idx_sanctioned_entities_source_active",
        ]
        
        for index_sql in indexes:
            db.execute(text(index_sql))
        
        logger.info("Performance indexes dropped")
    
    def _drop_change_detection_tables(self, db) -> None:
        """Drop change detection tables."""
        logger.info("Dropping change detection tables")
        
        tables = [
            "DROP TABLE IF EXISTS change_events CASCADE",
            "DROP TABLE IF EXISTS content_snapshots CASCADE", 
            "DROP TABLE IF EXISTS scraper_runs CASCADE"
        ]
        
        for table_sql in tables:
            db.execute(text(table_sql))
        
        logger.info("Change detection tables dropped")
    
    def _remove_content_hash_column(self, db) -> None:
        """Remove content_hash column from sanctioned_entities."""
        logger.info("Removing content_hash column")
        
        db.execute(text("""
            ALTER TABLE sanctioned_entities 
            DROP COLUMN IF EXISTS content_hash
        """))
        
        logger.info("content_hash column removed")
    
    # ======================== MIGRATION TRACKING ========================
    
    def _is_migration_applied(self, db) -> bool:
        """Check if migration has been applied."""
        try:
            # Check if change detection tables exist
            inspector = inspect(db.bind)
            tables = inspector.get_table_names()
            
            required_tables = ['change_events', 'scraper_runs', 'content_snapshots']
            return all(table in tables for table in required_tables)
            
        except Exception:
            return False
    
    def _record_migration(self, db) -> None:
        """Record migration in database."""
        # Create migrations table if it doesn't exist
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                migration_id VARCHAR(255) PRIMARY KEY,
                migration_name VARCHAR(255) NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                description TEXT
            )
        """))
        
        # Record this migration
        db.execute(text("""
            INSERT INTO schema_migrations (migration_id, migration_name, description)
            VALUES (:migration_id, :migration_name, :description)
            ON CONFLICT (migration_id) DO NOTHING
        """), {
            'migration_id': self.migration_id,
            'migration_name': self.migration_name,
            'description': MIGRATION_DESCRIPTION
        })
        
        logger.info(f"Migration {self.migration_id} recorded")
    
    def _remove_migration_record(self, db) -> None:
        """Remove migration record."""
        db.execute(text("""
            DELETE FROM schema_migrations 
            WHERE migration_id = :migration_id
        """), {'migration_id': self.migration_id})
        
        logger.info(f"Migration record {self.migration_id} removed")


# ======================== COMMAND LINE INTERFACE ========================

def run_migration():
    """Run the change detection migration."""
    print(f"TrustCheck Migration: {MIGRATION_NAME}")
    print("=" * 60)
    print(MIGRATION_DESCRIPTION)
    print("=" * 60)
    
    response = input("\nDo you want to proceed with the migration? (y/N): ").lower().strip()
    
    if response in ['y', 'yes']:
        try:
            migration = ChangeDetectionMigration()
            migration.upgrade()
            print("\n✅ Migration completed successfully!")
            print("Your database now supports change detection.")
        except Exception as e:
            print(f"\n❌ Migration failed: {e}")
            print("Please check the logs for more details.")
            return False
    else:
        print("Migration cancelled.")
        return False
    
    return True


def rollback_migration():
    """Rollback the change detection migration."""
    print(f"TrustCheck Migration Rollback: {MIGRATION_NAME}")
    print("=" * 60)
    print("⚠️  WARNING: This will remove all change detection data!")
    print("=" * 60)
    
    response = input("\nAre you sure you want to rollback? (y/N): ").lower().strip()
    
    if response in ['y', 'yes']:
        try:
            migration = ChangeDetectionMigration()
            migration.downgrade()
            print("\n✅ Migration rolled back successfully!")
        except Exception as e:
            print(f"\n❌ Rollback failed: {e}")
            return False
    else:
        print("Rollback cancelled.")
        return False
    
    return True


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        rollback_migration()
    else:
        run_migration()