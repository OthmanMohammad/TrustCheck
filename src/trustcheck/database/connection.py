"""
TrustCheck Database Connection.

Async SQLAlchemy database connection management for SQLite.
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from trustcheck.config import settings

logger = logging.getLogger(__name__)

# Global engine instance
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Get or create the database engine."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
            future=True,
            # SQLite specific settings
            connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
        )

        # Enable SQLite optimizations
        if "sqlite" in settings.database_url:

            @event.listens_for(_engine.sync_engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):  # type: ignore
                cursor = dbapi_connection.cursor()
                # Enable foreign keys
                cursor.execute("PRAGMA foreign_keys=ON")
                # Use WAL mode for better concurrency
                cursor.execute("PRAGMA journal_mode=WAL")
                # Increase cache size (negative = KB)
                cursor.execute("PRAGMA cache_size=-64000")
                # Synchronous mode for balance of safety and speed
                cursor.execute("PRAGMA synchronous=NORMAL")
                # Increase busy timeout
                cursor.execute("PRAGMA busy_timeout=5000")
                cursor.close()

        logger.info(f"Database engine created: {settings.database_url}")

    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the session factory."""
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database sessions."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_session_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for database sessions outside of FastAPI."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize the database (create tables if they don't exist)."""
    from trustcheck.database.models import Base

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized")


async def close_db() -> None:
    """Close database connections."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database connections closed")


async def check_db_connection() -> bool:
    """Check if database connection is working."""
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False
