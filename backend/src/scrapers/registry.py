"""
Centralized scraper registry for managing all scrapers.
Provides discovery, factory pattern, and metadata management.
"""

from typing import Dict, List, Type, Optional
from dataclasses import dataclass
from enum import Enum

# ======================== ENUMS AND DATA MODELS ========================

class ScraperTier(Enum):
    TIER1 = "tier1"  # Daily, critical
    TIER2 = "tier2"  # Weekly, important  
    TIER3 = "tier3"  # Monthly, regional

class Region(Enum):
    US = "us"
    EUROPE = "europe"
    ASIA_PACIFIC = "asia_pacific"
    INTERNATIONAL = "international"
    AMERICAS = "americas"
    AFRICA_MIDDLE_EAST = "africa_middle_east"

@dataclass
class ScraperMetadata:
    name: str
    region: Region
    tier: ScraperTier
    update_frequency: str
    entity_count: int
    complexity: str  # LOW, MEDIUM, HIGH
    data_format: str  # XML, JSON, CSV, Excel
    requires_auth: bool = False

# ======================== SCRAPER REGISTRY ========================

class ScraperRegistry:
    """Registry for all scrapers with metadata and factory methods."""
    
    def __init__(self):
        self._scrapers: Dict[str, Type] = {}
        self._metadata: Dict[str, ScraperMetadata] = {}
    
    # ======================== REGISTRATION METHODS ========================
    
    def register(self, scraper_class: Type, metadata: ScraperMetadata):
        """Register a scraper with metadata."""
        self._scrapers[metadata.name] = scraper_class
        self._metadata[metadata.name] = metadata
    
    # ======================== FACTORY METHODS ========================
    
    def get_scraper(self, name: str) -> Optional[Type]:
        """Get scraper class by name."""
        return self._scrapers.get(name)
    
    def create_scraper(self, name: str):
        """Create scraper instance by name."""
        scraper_class = self.get_scraper(name)
        if scraper_class:
            return scraper_class()
        return None
    
    # ======================== QUERY METHODS ========================
    
    def list_by_region(self, region: Region) -> List[str]:
        """Get all scrapers for a region."""
        return [
            name for name, meta in self._metadata.items() 
            if meta.region == region
        ]
    
    def list_by_tier(self, tier: ScraperTier) -> List[str]:
        """Get all scrapers for a tier."""
        return [
            name for name, meta in self._metadata.items() 
            if meta.tier == tier
        ]
    
    def get_all_scrapers(self) -> Dict[str, ScraperMetadata]:
        """Get all registered scrapers with metadata."""
        return self._metadata.copy()
    
    def list_available_scrapers(self) -> List[str]:
        """Get list of all available scraper names."""
        return list(self._scrapers.keys())

# ======================== GLOBAL REGISTRY INSTANCE ========================

# Global registry instance
scraper_registry = ScraperRegistry()