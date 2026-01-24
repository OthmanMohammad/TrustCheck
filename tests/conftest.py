"""
TrustCheck Test Configuration.

Pytest fixtures and configuration.
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    from trustcheck.database.models import Base

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
def sample_entity_data() -> dict:
    """Sample entity data for testing."""
    return {
        "source_uid": "TEST-001",
        "primary_name": "John Doe Smith",
        "entity_type": "INDIVIDUAL",
        "names": [
            {"value": "John Doe Smith", "type": "PRIMARY"},
            {"value": "J.D. Smith", "type": "ALIAS"},
        ],
        "addresses": [
            {
                "country": "US",
                "city": "New York",
                "full_address": "123 Main St, New York, US",
            }
        ],
        "identifiers": [
            {"type": "PASSPORT", "value": "AB123456", "country": "US"}
        ],
        "programs": ["SDGT", "IRAN"],
        "nationality": "US",
    }


@pytest.fixture
def sample_names() -> list[tuple[str, str]]:
    """Sample names for matching tests."""
    return [
        ("John Smith", "JOHN SMITH"),
        ("Mohammad Ali Khan", "MOHAMMAD ALI KHAN"),
        ("Владимир Путин", "VLADIMIR PUTIN"),  # Cyrillic
        ("محمد", "MHD"),  # Arabic
        ("José García", "JOSE GARCIA"),  # Diacritics
        ("Dr. Jane Doe, PhD", "JANE DOE"),  # Titles/suffixes
    ]
