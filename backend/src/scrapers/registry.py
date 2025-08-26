"""
Centralized scraper registry - Updated for new architecture

Provides discovery, factory pattern, and metadata management.
"""

from typing import Dict, List, Type, Optional
from dataclasses import dataclass
from enum import Enum

from src.utils.logging import get_logger

# ======================== ENUMS AND DATA MODELS ========================

class ScraperTier(Enum):
    TIER1 = "TIER1"  # Daily, critical
    TIER2 = "TIER2"  # Weekly, important  
    TIER3 = "TIER3"  # Monthly, regional

class Region(Enum):
    US = "US"
    EUROPE = "EUROPE"
    ASIA_PACIFIC = "ASIA_PACIFIC"
    INTERNATIONAL = "INTERNATIONAL"
    AMERICAS = "AMERICAS"
    AFRICA_MIDDLE_EAST = "AFRICA_MIDDLE_EAST"

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
        self.logger = get_logger("scraper.registry")
    
    # ======================== REGISTRATION METHODS ========================
    
    def register(self, scraper_class: Type, metadata: ScraperMetadata):
        """Register a scraper with metadata."""
        self._scrapers[metadata.name] = scraper_class
        self._metadata[metadata.name] = metadata
        self.logger.info(f"Registered scraper: {metadata.name} ({metadata.region.value})")
    
    # ======================== FACTORY METHODS ========================
    
    def get_scraper(self, name: str) -> Optional[Type]:
        """Get scraper class by name."""
        return self._scrapers.get(name)
    
    def create_scraper(self, name: str):
        """Create scraper instance by name."""
        scraper_class = self.get_scraper(name)
        if scraper_class:
            try:
                instance = scraper_class()
                self.logger.debug(f"Created scraper instance: {name}")
                return instance
            except Exception as e:
                self.logger.error(f"Failed to create scraper {name}: {e}")
                return None
        else:
            self.logger.warning(f"Scraper not found: {name}")
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
    
    def get_all_scrapers(self) -> Dict[str, Dict[str, str]]:
        """Get all registered scrapers with metadata as serializable dict."""
        scrapers_data = {}
        for name, metadata in self._metadata.items():
            scrapers_data[name] = {
                "name": metadata.name,
                "region": metadata.region.value,
                "tier": metadata.tier.value,
                "update_frequency": metadata.update_frequency,
                "entity_count": metadata.entity_count,
                "complexity": metadata.complexity,
                "data_format": metadata.data_format,
                "requires_auth": metadata.requires_auth
            }
        return scrapers_data
    
    def list_available_scrapers(self) -> List[str]:
        """Get list of all available scraper names."""
        return list(self._scrapers.keys())
    
    def get_metadata(self, name: str) -> Optional[ScraperMetadata]:
        """Get metadata for a specific scraper."""
        return self._metadata.get(name)
    
    def get_scrapers_by_complexity(self, complexity: str) -> List[str]:
        """Get scrapers by complexity level."""
        return [
            name for name, meta in self._metadata.items()
            if meta.complexity.upper() == complexity.upper()
        ]
    
    def get_high_priority_scrapers(self) -> List[str]:
        """Get TIER1 scrapers that should run most frequently."""
        return self.list_by_tier(ScraperTier.TIER1)

# ======================== GLOBAL REGISTRY INSTANCE ========================

# Global registry instance
scraper_registry = ScraperRegistry()

# ======================== AUTO-REGISTRATION ========================

def auto_register_scrapers():
    """Automatically register all available scrapers."""
    try:
        # Import all scraper modules to trigger registration
        from src.scrapers.implementations.ofac_scraper import OFACScraper
        # Add more imports here as you add scrapers
        
        scraper_registry.logger.info(f"Auto-registration completed: {len(scraper_registry.list_available_scrapers())} scrapers registered")
        
    except Exception as e:
        scraper_registry.logger.error(f"Auto-registration failed: {e}")

# Auto-register on import
auto_register_scrapers()