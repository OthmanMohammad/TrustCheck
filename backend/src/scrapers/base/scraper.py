"""
Abstract base scraper framework for all sanctions sources.
Implements common patterns: download, parse, validate, store.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

# ======================== DATA MODELS ========================

@dataclass
class ScrapingResult:
    """Standard result format for all scrapers."""
    source: str
    entities_processed: int
    entities_added: int
    entities_updated: int
    entities_removed: int
    duration_seconds: float
    status: str  # SUCCESS, FAILED, PARTIAL
    error_message: Optional[str] = None

# ======================== BASE SCRAPER CLASS ========================

class BaseScraper(ABC):
    """Abstract base class for all sanctions scrapers."""
    
    def __init__(self, source_name: str):
        self.source_name = source_name
        self.logger = logging.getLogger(f"scraper.{source_name}")
    
    # ======================== ABSTRACT METHODS ========================
    
    @abstractmethod
    def download_data(self) -> str:
        """Download raw data from source."""
        pass
    
    @abstractmethod
    def parse_entities(self, raw_data: str) -> List[Any]:
        """Parse raw data into structured entities."""
        pass
    
    @abstractmethod
    def store_entities(self, entities: List[Any]) -> None:
        """Store entities in database."""
        pass
    
    # ======================== MAIN WORKFLOW ========================
    
    def scrape_and_store(self) -> ScrapingResult:
        """Main scraping workflow with error handling."""
        start_time = datetime.utcnow()
        
        try:
            self.logger.info(f"Starting scraping for {self.source_name}")
            
            # Download raw data
            raw_data = self.download_data()
            
            # Parse into structured entities
            entities = self.parse_entities(raw_data)
            
            # Store in database
            self.store_entities(entities)
            
            # Calculate duration
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            # Create success result
            result = ScrapingResult(
                source=self.source_name,
                entities_processed=len(entities),
                entities_added=len(entities),  # TODO: Track actual changes
                entities_updated=0,
                entities_removed=0,
                duration_seconds=duration,
                status="SUCCESS"
            )
            
            self.logger.info(f"Scraping completed: {len(entities)} entities in {duration:.1f}s")
            return result
            
        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            self.logger.error(f"Scraping failed after {duration:.1f}s: {e}")
            
            return ScrapingResult(
                source=self.source_name,
                entities_processed=0,
                entities_added=0,
                entities_updated=0,
                entities_removed=0,
                duration_seconds=duration,
                status="FAILED",
                error_message=str(e)
            )
