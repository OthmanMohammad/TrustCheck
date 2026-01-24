"""
TrustCheck Scrapers Module.

Scrapers for various sanctions data sources.
"""

from trustcheck.domain import DataSource
from trustcheck.scrapers.base import BaseScraper, RawEntity, ScrapeResult
from trustcheck.scrapers.eu import EUScraper
from trustcheck.scrapers.ofac import OFACScraper
from trustcheck.scrapers.uk import UKScraper
from trustcheck.scrapers.un import UNScraper

# Registry of available scrapers
SCRAPERS: dict[DataSource, type[BaseScraper]] = {
    DataSource.OFAC_SDN: OFACScraper,
    DataSource.UN: UNScraper,
    DataSource.EU: EUScraper,
    DataSource.UK: UKScraper,
}


def get_scraper(source: DataSource) -> BaseScraper:
    """Get a scraper instance for a data source."""
    scraper_class = SCRAPERS.get(source)
    if not scraper_class:
        raise ValueError(f"No scraper available for source: {source}")
    return scraper_class()


def get_all_scrapers() -> list[BaseScraper]:
    """Get all available scraper instances."""
    return [cls() for cls in SCRAPERS.values()]


__all__ = [
    "BaseScraper",
    "RawEntity",
    "ScrapeResult",
    "OFACScraper",
    "UNScraper",
    "EUScraper",
    "UKScraper",
    "SCRAPERS",
    "get_scraper",
    "get_all_scrapers",
]
