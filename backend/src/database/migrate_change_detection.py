"""
Database Migration for Change Detection

Adds the new change detection tables to existing TrustCheck database.
Run this script to upgrade your database schema.
"""

import logging
from sqlalchemy import text, inspect
from src.database.connection import db_manager
from src.database.models import Base, ContentSnapshot, ChangeEvent, ScraperRun

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ======================== MIGRATION FUNCTIONS ========================

def check_table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    try:
        with db_manager.get_session() as db:
            inspector = inspect(db.bind)
            return table_name in inspector.get_table_names()
    except Exception as e:
        logger.error(f"Error checking table {table_name}: {e}")
        return False

def add_content_hash_column():
    """Add content_hash column to existing sanctioned_entities table."""
    try:
        with db_manager.get_session() as db:
            # Check if column already exists
            inspector = inspect(db.bind)
            columns = inspector.get_columns('sanctioned_entities')
            column_names = [col['name'] for col in columns]
            
            if 'content_hash' not in column_names:
                logger.info("Adding content_hash column to sanctioned_entities...")
                db.execute(text("""
                    ALTER TABLE sanctioned_entities 
                    ADD COLUMN content_hash VARCHAR(64);
                """))
                db.commit()
                logger.info("✅ Added content_hash column")
            else:
                logger.info("content_hash column already exists")
                
    except Exception as e:
        logger.error(f"Failed to add content_hash column: {e}")
        raise

def create_change_detection_tables():
    """Create all change detection tables."""
    try:
        logger.info("Creating change detection tables...")
        
        # Create tables using SQLAlchemy
        Base.metadata.create_all(bind=db_manager.engine, tables=[
            ContentSnapshot.__table__,
            ChangeEvent.__table__, 
            ScraperRun.__table__
        ])
        
        logger.info("✅ Change detection tables created successfully")
        
    except Exception as e:
        logger.error(f"Failed to create change detection tables: {e}")
        raise

def create_indexes():
    """Create additional indexes for performance."""
    try:
        logger.info("Creating performance indexes...")
        
        with db_manager.get_session() as db:
            # Indexes for change_events
            db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_change_events_time 
                ON change_events(detected_at DESC);
            """))
            
            db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_change_events_risk 
                ON change_events(risk_level, detected_at DESC);
            """))
            
            db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_change_events_source_type 
                ON change_events(source, change_type, detected_at);
            """))
            
            # Indexes for content_snapshots
            db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_content_snapshots_source 
                ON content_snapshots(source, snapshot_time DESC);
            """))
            
            # Indexes for scraper_runs
            db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_scraper_runs_source_time 
                ON scraper_runs(source, started_at DESC);
            """))
            
            db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_scraper_runs_status 
                ON scraper_runs(status, started_at DESC);
            """))
            
            db.commit()
            logger.info("✅ Performance indexes created successfully")
            
    except Exception as e:
        logger.error(f"Failed to create indexes: {e}")
        raise

def verify_migration():
    """Verify that migration completed successfully."""
    try:
        logger.info("Verifying migration...")
        
        # Check all tables exist
        required_tables = ['content_snapshots', 'change_events', 'scraper_runs']
        missing_tables = []
        
        for table in required_tables:
            if not check_table_exists(table):
                missing_tables.append(table)
        
        if missing_tables:
            raise Exception(f"Missing tables after migration: {missing_tables}")
        
        # Check content_hash column exists
        with db_manager.get_session() as db:
            inspector = inspect(db.bind)
            columns = inspector.get_columns('sanctioned_entities')
            column_names = [col['name'] for col in columns]
            
            if 'content_hash' not in column_names:
                raise Exception("content_hash column missing from sanctioned_entities")
        
        # Test basic operations
        with db_manager.get_session() as db:
            # Try to query each table
            db.execute(text("SELECT COUNT(*) FROM content_snapshots")).fetchone()
            db.execute(text("SELECT COUNT(*) FROM change_events")).fetchone()
            db.execute(text("SELECT COUNT(*) FROM scraper_runs")).fetchone()
        
        logger.info("✅ Migration verification passed")
        return True
        
    except Exception as e:
        logger.error(f"Migration verification failed: {e}")
        return False

# ======================== MAIN MIGRATION FUNCTION ========================

def run_migration():
    """
    Run the complete change detection migration.
    
    This function:
    1. Adds content_hash column to existing sanctioned_entities
    2. Creates new change detection tables
    3. Creates performance indexes  
    4. Verifies everything worked
    """
    
    logger.info("=" * 50)
    logger.info("TrustCheck Change Detection Migration")
    logger.info("=" * 50)
    
    try:
        # Check database connection
        if not db_manager.check_connection():
            raise Exception("Cannot connect to database")
        
        logger.info("Database connection verified")
        
        # Step 1: Add content_hash column to existing table
        logger.info("\nStep 1: Updating existing tables...")
        add_content_hash_column()
        
        # Step 2: Create new change detection tables
        logger.info("\nStep 2: Creating change detection tables...")
        create_change_detection_tables()
        
        # Step 3: Create performance indexes
        logger.info("\nStep 3: Creating performance indexes...")
        create_indexes()
        
        # Step 4: Verify migration
        logger.info("\nStep 4: Verifying migration...")
        if not verify_migration():
            raise Exception("Migration verification failed")
        
        logger.info("\n" + "=" * 50)
        logger.info("✅ MIGRATION COMPLETED SUCCESSFULLY")
        logger.info("=" * 50)
        logger.info("Your database now supports change detection!")
        logger.info("You can now run scrapers with automatic change tracking.")
        
    except Exception as e:
        logger.error(f"\n❌ MIGRATION FAILED: {e}")
        logger.error("Please check the error above and try again.")
        raise

# ======================== CLI ENTRY POINT ========================

if __name__ == "__main__":
    """Run migration when script is executed directly."""
    
    print("TrustCheck Change Detection Migration")
    print("This will add change detection capabilities to your database.")
    
    response = input("\nDo you want to proceed? (y/N): ").lower().strip()
    
    if response in ['y', 'yes']:
        try:
            run_migration()
            print("\n✅ Migration completed! Your database is ready for change detection.")
        except Exception as e:
            print(f"\n❌ Migration failed: {e}")
            exit(1)
    else:
        print("Migration cancelled.")
        exit(0)