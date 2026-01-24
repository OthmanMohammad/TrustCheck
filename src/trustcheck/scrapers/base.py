"""
TrustCheck Base Scraper.

Abstract base class for all sanctions list scrapers.
"""

import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

from trustcheck.config import settings
from trustcheck.domain import DataSource, EntityType, ScraperError

logger = logging.getLogger(__name__)


@dataclass
class RawEntity:
    """Raw entity data extracted from a sanctions list."""

    source_uid: str
    primary_name: str
    entity_type: EntityType
    names: list[dict[str, str]] = field(default_factory=list)  # [{"value": "...", "type": "..."}]
    addresses: list[dict[str, str]] = field(default_factory=list)
    identifiers: list[dict[str, str]] = field(default_factory=list)
    programs: list[str] = field(default_factory=list)
    date_of_birth: str | None = None
    place_of_birth: str | None = None
    nationality: str | None = None
    remarks: str | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScrapeResult:
    """Result of a scraping operation."""

    source: DataSource
    success: bool
    entities: list[RawEntity] = field(default_factory=list)
    content_hash: str = ""
    error_message: str | None = None
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    download_time_ms: float = 0.0
    parse_time_ms: float = 0.0


class BaseScraper(ABC):
    """Abstract base class for sanctions list scrapers."""

    def __init__(self) -> None:
        self.timeout = settings.scraping_timeout
        self.max_retries = settings.scraping_max_retries
        self.user_agent = settings.scraping_user_agent

    @property
    @abstractmethod
    def source(self) -> DataSource:
        """The data source this scraper handles."""
        pass

    @property
    @abstractmethod
    def url(self) -> str:
        """The URL to scrape."""
        pass

    async def scrape(self) -> ScrapeResult:
        """
        Execute the scraping operation.

        Returns:
            ScrapeResult with entities and metadata
        """
        result = ScrapeResult(source=self.source, success=False)
        start_time = datetime.utcnow()

        try:
            # Download content
            logger.info(f"Downloading {self.source.value} from {self.url}")
            download_start = datetime.utcnow()
            content = await self._download()
            download_end = datetime.utcnow()
            result.download_time_ms = (download_end - download_start).total_seconds() * 1000

            # Calculate content hash
            result.content_hash = self._hash_content(content)
            logger.info(f"Downloaded {len(content)} bytes, hash: {result.content_hash[:16]}...")

            # Parse content
            parse_start = datetime.utcnow()
            entities = await self._parse(content)
            parse_end = datetime.utcnow()
            result.parse_time_ms = (parse_end - parse_start).total_seconds() * 1000

            result.entities = entities
            result.success = True
            logger.info(f"Parsed {len(entities)} entities from {self.source.value}")

        except Exception as e:
            logger.exception(f"Error scraping {self.source.value}: {e}")
            result.error_message = str(e)
            result.success = False

        result.completed_at = datetime.utcnow()
        return result

    def _get_headers(self) -> dict[str, str]:
        """Get HTTP headers for the request."""
        return {
            "User-Agent": self.user_agent,
            "Accept": "application/xml,application/json,text/xml,text/html,*/*;q=0.9",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
        }

    async def _download(self) -> bytes:
        """Download content from the URL with retries."""
        last_error = None
        headers = self._get_headers()

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(self.timeout),
                    follow_redirects=True,
                    http2=True,  # Enable HTTP/2 for better compatibility
                ) as client:
                    response = await client.get(self.url, headers=headers)
                    response.raise_for_status()
                    return response.content

            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(f"Timeout downloading {self.url} (attempt {attempt + 1}/{self.max_retries})")
            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(f"HTTP error {e.response.status_code} downloading {self.url}")
                if e.response.status_code < 500:
                    # Client error, don't retry
                    break
            except Exception as e:
                last_error = e
                logger.warning(f"Error downloading {self.url}: {e}")

        raise ScraperError(self.source.value, f"Failed to download after {self.max_retries} attempts: {last_error}")

    @abstractmethod
    async def _parse(self, content: bytes) -> list[RawEntity]:
        """
        Parse the downloaded content into entities.

        Args:
            content: Raw bytes downloaded from the URL

        Returns:
            List of RawEntity objects
        """
        pass

    def _hash_content(self, content: bytes) -> str:
        """Calculate SHA-256 hash of content."""
        return hashlib.sha256(content).hexdigest()

    def _detect_entity_type(self, type_str: str | None) -> EntityType:
        """Detect entity type from string."""
        if not type_str:
            return EntityType.UNKNOWN

        type_lower = type_str.lower()

        if any(t in type_lower for t in ["individual", "person", "human"]):
            return EntityType.INDIVIDUAL
        elif any(t in type_lower for t in ["entity", "organization", "company", "corporate", "business"]):
            return EntityType.ORGANIZATION
        elif any(t in type_lower for t in ["vessel", "ship", "boat"]):
            return EntityType.VESSEL
        elif any(t in type_lower for t in ["aircraft", "airplane", "plane"]):
            return EntityType.AIRCRAFT
        else:
            return EntityType.UNKNOWN

    def _clean_text(self, text: str | None) -> str | None:
        """Clean and normalize text."""
        if not text:
            return None
        # Remove extra whitespace
        cleaned = " ".join(text.split())
        return cleaned if cleaned else None
