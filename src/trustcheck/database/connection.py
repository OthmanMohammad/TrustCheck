"""
TrustCheck Database Connection.

Enterprise-grade async database connection management.
Supports PostgreSQL (recommended) and SQLite (development only).
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from trustcheck.config import settings

logger = logging.getLogger(__name__)

# Global engine instance
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _normalize_database_url(url: str) -> str:
    """
    Normalize database URL for asyncpg compatibility.

    Neon and other providers use 'sslmode' but asyncpg uses 'ssl'.
    This converts the URL to work with asyncpg.
    """
    from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

    parsed = urlparse(url)

    # Parse query parameters
    params = parse_qs(parsed.query, keep_blank_values=True)

    # Convert sslmode to ssl for asyncpg
    if 'sslmode' in params:
        sslmode = params.pop('sslmode')[0]
        # asyncpg uses 'ssl' parameter: 'require', 'prefer', 'disable', etc.
        if sslmode in ('require', 'verify-ca', 'verify-full'):
            params['ssl'] = ['require']
        elif sslmode == 'prefer':
            params['ssl'] = ['prefer']
        elif sslmode == 'disable':
            params['ssl'] = ['disable']

    # Remove channel_binding (not supported by asyncpg directly)
    params.pop('channel_binding', None)

    # Rebuild query string
    new_query = urlencode({k: v[0] for k, v in params.items()}) if params else ''

    # Rebuild URL
    new_parsed = parsed._replace(query=new_query)
    return urlunparse(new_parsed)


def _create_postgresql_engine() -> AsyncEngine:
    """Create PostgreSQL engine with proper connection pooling."""
    # Normalize URL for asyncpg compatibility (handle sslmode -> ssl conversion)
    normalized_url = _normalize_database_url(settings.database_url)

    engine = create_async_engine(
        normalized_url,
        echo=settings.db_echo,
        future=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_pool_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    logger.info(
        f"PostgreSQL engine created with pool_size={settings.db_pool_size}, "
        f"max_overflow={settings.db_pool_max_overflow}"
    )
    return engine


def _create_sqlite_engine() -> AsyncEngine:
    """Create SQLite engine (development only)."""
    logger.warning(
        "Using SQLite - NOT RECOMMENDED FOR PRODUCTION. "
        "SQLite has single-writer limitation causing lock errors under load."
    )
    engine = create_async_engine(
        settings.database_url,
        echo=settings.db_echo,
        future=True,
        poolclass=NullPool,  # No pooling for SQLite
        connect_args={
            "check_same_thread": False,
            "timeout": 60,
        },
    )

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection: Any, connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA cache_size=-64000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=60000")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.execute("PRAGMA mmap_size=268435456")
        cursor.close()

    return engine


def get_engine() -> AsyncEngine:
    """Get or create the database engine."""
    global _engine
    if _engine is None:
        if settings.is_postgresql:
            _engine = _create_postgresql_engine()
        else:
            _engine = _create_sqlite_engine()
        logger.info(f"Database engine created: {settings.database_url.split('@')[-1]}")
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
    """Dependency for getting database sessions (FastAPI)."""
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
    """Initialize the database (create tables and extensions)."""
    from trustcheck.database.models import Base

    engine = get_engine()

    async with engine.begin() as conn:
        # For PostgreSQL, enable required extensions
        if settings.is_postgresql:
            await _init_postgresql_extensions(conn)

        # Create all tables
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database tables initialized")


async def _init_postgresql_extensions(conn: AsyncConnection) -> None:
    """Initialize PostgreSQL extensions for fuzzy search."""
    try:
        # pg_trgm for trigram similarity (fuzzy text search)
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        logger.info("PostgreSQL pg_trgm extension enabled")

        # unaccent for diacritic-insensitive search
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent"))
        logger.info("PostgreSQL unaccent extension enabled")

    except Exception as e:
        logger.warning(f"Could not create PostgreSQL extensions: {e}")


async def create_search_indexes() -> None:
    """Create optimized indexes for search operations."""
    if not settings.is_postgresql:
        logger.info("Skipping search indexes - only available for PostgreSQL")
        return

    engine = get_engine()
    async with engine.begin() as conn:
        try:
            # GIN index for trigram similarity on normalized names
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_names_trgm
                ON names USING gin (name_normalized gin_trgm_ops)
            """))

            # GIN index for trigram on primary name
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_entities_name_trgm
                ON entities USING gin (primary_name_normalized gin_trgm_ops)
            """))

            # B-tree indexes for common filters
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_entities_active
                ON entities (is_active) WHERE is_active = true
            """))

            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_entities_type
                ON entities (entity_type)
            """))

            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_source_records_source_active
                ON source_records (source, is_active) WHERE is_active = true
            """))

            logger.info("PostgreSQL search indexes created")

        except Exception as e:
            logger.error(f"Error creating search indexes: {e}")
            raise


async def close_db() -> None:
    """Close database connections."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database connections closed")


async def check_db_connection() -> dict[str, Any]:
    """
    Check database connection health.

    Returns:
        Dict with connection status and details
    """
    result = {
        "connected": False,
        "database_type": "postgresql" if settings.is_postgresql else "sqlite",
        "extensions": [],
        "error": None,
    }

    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            result["connected"] = True

            # Check PostgreSQL extensions
            if settings.is_postgresql:
                ext_result = await conn.execute(text(
                    "SELECT extname FROM pg_extension WHERE extname IN ('pg_trgm', 'unaccent')"
                ))
                result["extensions"] = [row[0] for row in ext_result.fetchall()]

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Database connection check failed: {e}")

    return result
