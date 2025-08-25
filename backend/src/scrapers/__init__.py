"""
Scrapers package with automatic registration.
Import this module to ensure all scrapers are registered.
"""

from src.scrapers.registry import scraper_registry

# Import all scraper modules to trigger registration
from src.scrapers.us.ofac.scraper import OFACScraper

__all__ = ['scraper_registry', 'OFACScraper']