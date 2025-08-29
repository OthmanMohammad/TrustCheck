"""
Database Connection - Fully Async
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from contextlib import asynccontextmanager
import logging
from typing import AsyncGenerator
from sqlalchemy import text

from src.infrastructure.database.models import Base
from src.core.config import settings

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Fully async database manager."""
    
    def __init__(self):
        self.engine = None
        self.AsyncSessionLocal = None
        self._initialize_engine()
    
    def _initialize_engine(self):
        """Initialize PostgreSQL async engine."""
        # Convert to async URL
        database_url = settings.database.database_url
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
        
        logger.info(f"🔌 Connecting to PostgreSQL (async): {settings.database.host}:{settings.database.port}/{settings.database.name}")
        
        self.engine = create_async_engine(
            database_url,
            pool_size=settings.database.pool_size,
            max_overflow=settings.database.max_overflow,
            pool_timeout=settings.database.pool_timeout,
            pool_recycle=settings.database.pool_recycle,
            pool_pre_ping=True,
            echo=settings.debug,
            future=True
        )
        
        self.AsyncSessionLocal = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        logger.info("✅ Async database engine initialized")
    
    async def create_tables(self):
        """Create all database tables."""
        try:
            logger.info("🏗️ Creating database tables...")
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("✅ Database tables created successfully")
        except Exception as e:
            logger.error(f"❌ Failed to create database tables: {e}")
            raise
    
    async def check_connection(self) -> bool:
        """Check if database connection is healthy."""
        try:
            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
                return True
        except Exception as e:
            logger.error(f"❌ Database connection check failed: {e}")
            return False
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get async database session."""
        async with self.AsyncSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def close(self):
        """Close database connections."""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connections closed")

# Global database manager instance
db_manager = DatabaseManager()

# FastAPI dependency
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for getting async database sessions."""
    async with db_manager.AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# Lifecycle functions
async def init_db():
    """Initialize database on startup."""
    await db_manager.create_tables()
    logger.info("Database initialized")

async def close_db():
    """Close database on shutdown."""
    await db_manager.close()

__all__ = ['get_db', 'init_db', 'close_db', 'db_manager', 'DatabaseManager']