from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
import logging
import time
from typing import Generator

from .models import Base
from src.core.config import settings

logger = logging.getLogger(__name__)

class DatabaseManager:
    """database manager with connection pooling and monitoring."""
    
    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self._initialize_engine()
        self._setup_event_listeners()
    
    def _initialize_engine(self):
        """Initialize PostgreSQL engine."""
        
        logger.info(f"🔌 Connecting to PostgreSQL: {settings.database.host}:{settings.database.port}/{settings.database.name}")
        
        # Production engine configuration
        self.engine = create_engine(
            settings.database.database_url,  # FIXED: Use nested database settings
            
            # Connection Pool Settings
            poolclass=QueuePool,
            pool_size=settings.database.pool_size,         # FIXED: Use nested settings
            max_overflow=settings.database.max_overflow,   # FIXED: Use nested settings
            pool_timeout=settings.database.pool_timeout,   # FIXED: Use nested settings
            pool_recycle=settings.database.pool_recycle,   # FIXED: Use nested settings
            pool_pre_ping=True,  # Verify connections before use
            
            # Performance Settings
            echo=settings.debug,  # Log SQL queries in debug mode
            echo_pool=settings.debug,  # Log connection pool activity
            future=True,  # Use SQLAlchemy 2.0 style
            
            # Connection Settings - FIXED for psycopg2
            connect_args={
                "connect_timeout": 10,
                "application_name": "TrustCheck-API",
            }
        )
        
        # Session factory
        self.SessionLocal = sessionmaker(
            autocommit=False, 
            autoflush=False, 
            bind=self.engine
        )
        
        logger.info("✅ Database engine initialized successfully")
    
    def _setup_event_listeners(self):
        """Set up SQLAlchemy event listeners for monitoring."""
        
        @event.listens_for(self.engine, "connect")
        def set_connection_pragma(dbapi_connection, connection_record):
            """Configure connection settings."""
            if settings.debug:
                logger.debug("🔗 New database connection established")
        
        @event.listens_for(self.engine, "checkout")
        def receive_checkout(dbapi_connection, connection_record, connection_proxy):
            """Monitor connection checkout."""
            if settings.debug:
                logger.debug("📤 Database connection checked out from pool")
        
        @event.listens_for(self.engine, "checkin")
        def receive_checkin(dbapi_connection, connection_record):
            """Monitor connection checkin."""
            if settings.debug:
                logger.debug("📥 Database connection returned to pool")
    
    def create_tables(self):
        """Create all database tables with error handling."""
        try:
            logger.info("🏗️ Creating database tables...")
            Base.metadata.create_all(bind=self.engine)
            logger.info("✅ Database tables created successfully")
        except Exception as e:
            logger.error(f"❌ Failed to create database tables: {e}")
            raise
    
    def check_connection(self) -> bool:
        """Check if database connection is healthy."""
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
                return True
        except Exception as e:
            logger.error(f"❌ Database connection check failed: {e}")
            return False
    
    def get_pool_status(self) -> dict:
        """Get connection pool status for monitoring."""
        pool = self.engine.pool
        return {
            "pool_size": pool.size(),
            "checked_in_connections": pool.checkedin(),
            "checked_out_connections": pool.checkedout(),
            "overflow_connections": pool.overflow(),
            "total_connections": pool.checkedin() + pool.checkedout()
        }
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        Get database session with automatic cleanup and error handling.
        
        Usage:
            with db_manager.get_session() as session:
                # Use session
                pass
        """
        session = self.SessionLocal()
        try:
            yield session
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()

# Global database manager instance
db_manager = DatabaseManager()

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for getting database sessions.
    
    Yields:
        Database session with automatic cleanup.
    """
    session = db_manager.SessionLocal()
    try:
        yield session
    except Exception as e:
        session.rollback()
        logger.error(f"Database error in API endpoint: {e}")
        raise
    finally:
        session.close()

def create_tables():
    """Create all database tables."""
    db_manager.create_tables()

def check_db_health() -> bool:
    """Check database health for monitoring endpoints."""
    return db_manager.check_connection()

def get_db_stats() -> dict:
    """Get database statistics for monitoring."""
    return {
        "connection_pool": db_manager.get_pool_status(),
        "healthy": check_db_health(),
        "database_url": f"postgresql://{settings.database.host}:{settings.database.port}/{settings.database.name}"  # FIXED: Use nested settings
    }

async def init_db():
    """Initialize database connection for async context."""
    # For now, just ensure connection is ready
    db_manager._initialize_engine()
    logger.info("Database initialized for application startup")

async def close_db():
    """Close database connections on shutdown."""
    if db_manager._engine:
        db_manager._engine.dispose()
        logger.info("Database connections closed")