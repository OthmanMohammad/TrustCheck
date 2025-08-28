from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import QueuePool, NullPool
from contextlib import contextmanager, asynccontextmanager
import logging
import time
from typing import Generator, AsyncGenerator

from .models import Base
from src.core.config import settings

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Database manager with connection pooling and monitoring - supports both sync and async."""
    
    def __init__(self):
        self.engine = None
        self.async_engine = None
        self.SessionLocal = None
        self.AsyncSessionLocal = None
        self._initialize_engine()
        self._initialize_async_engine()
        self._setup_event_listeners()
    
    def _initialize_engine(self):
        """Initialize PostgreSQL sync engine."""
        
        logger.info(f"🔌 Connecting to PostgreSQL: {settings.database.host}:{settings.database.port}/{settings.database.name}")
        
        # Production engine configuration
        self.engine = create_engine(
            settings.database.database_url,
            
            # Connection Pool Settings
            poolclass=QueuePool,
            pool_size=settings.database.pool_size,
            max_overflow=settings.database.max_overflow,
            pool_timeout=settings.database.pool_timeout,
            pool_recycle=settings.database.pool_recycle,
            pool_pre_ping=True,  # Verify connections before use
            
            # Performance Settings
            echo=settings.debug,  # Log SQL queries in debug mode
            echo_pool=settings.debug,  # Log connection pool activity
            future=True,  # Use SQLAlchemy 2.0 style
            
            # Connection Settings for psycopg2
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
        
        logger.info("✅ Sync database engine initialized successfully")
    
    def _initialize_async_engine(self):
        """Initialize PostgreSQL async engine."""
        try:
            # Convert to async URL
            async_url = settings.database.database_url.replace(
                "postgresql://", "postgresql+asyncpg://"
            )
            
            logger.info("🔌 Initializing async database engine...")
            
            self.async_engine = create_async_engine(
                async_url,
                poolclass=NullPool,  # Use NullPool for async to avoid connection issues
                echo=settings.debug,
                future=True
            )
            
            # Async session factory
            self.AsyncSessionLocal = async_sessionmaker(
                self.async_engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            logger.info("✅ Async database engine initialized successfully")
        except Exception as e:
            logger.warning(f"⚠️ Async engine initialization failed (install asyncpg if needed): {e}")
            self.async_engine = None
            self.AsyncSessionLocal = None
    
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
    
    async def check_async_connection(self) -> bool:
        """Check if async database connection is healthy."""
        if not self.async_engine:
            return False
        try:
            async with self.async_engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
                return True
        except Exception as e:
            logger.error(f"❌ Async database connection check failed: {e}")
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
        Get sync database session with automatic cleanup and error handling.
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
    
    @asynccontextmanager
    async def get_async_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get async database session with automatic cleanup and error handling.
        """
        if not self.AsyncSessionLocal:
            raise RuntimeError("Async database not initialized. Install asyncpg: pip install asyncpg")
        
        async with self.AsyncSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Async database session error: {e}")
                raise
            finally:
                await session.close()

# Global database manager instance
db_manager = DatabaseManager()

# ======================== SYNC FUNCTIONS (for v1 API) ========================

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for getting sync database sessions (v1 API).
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
        "database_url": f"postgresql://{settings.database.host}:{settings.database.port}/{settings.database.name}"
    }

# ======================== ASYNC FUNCTIONS (for v2 API) ========================

async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for getting async database sessions (v2 API).
    """
    if not db_manager.AsyncSessionLocal:
        # Fallback to sync session wrapped in async (not ideal but works)
        session = db_manager.SessionLocal()
        try:
            yield session
        except Exception as e:
            session.rollback()
            logger.error(f"Database error in async endpoint: {e}")
            raise
        finally:
            session.close()
    else:
        async with db_manager.get_async_session() as session:
            yield session

async def check_async_db_health() -> bool:
    """Check async database health."""
    if db_manager.async_engine:
        return await db_manager.check_async_connection()
    else:
        # Fallback to sync check
        return db_manager.check_connection()

async def init_db():
    """Initialize database connection for async context."""
    db_manager._initialize_engine()
    if db_manager.async_engine:
        async with db_manager.async_engine.begin() as conn:
            # Test connection
            await conn.run_sync(lambda conn: None)
    logger.info("Database initialized for application startup")

async def close_db():
    """Close database connections on shutdown."""
    if db_manager.engine:
        db_manager.engine.dispose()
    if db_manager.async_engine:
        await db_manager.async_engine.dispose()
    logger.info("Database connections closed")

# ======================== EXPORTS ========================

__all__ = [
    # Sync functions
    'get_db',
    'create_tables',
    'check_db_health',
    'get_db_stats',
    
    # Async functions
    'get_async_db',
    'check_async_db_health',
    'init_db',
    'close_db',
    
    # Manager
    'db_manager',
    'DatabaseManager'
]