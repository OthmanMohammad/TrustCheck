"""
Download Manager Service

Handles content retrieval with optimization and error handling.
Provides content hashing and change detection support.
"""

import hashlib
import requests
from typing import Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from sqlalchemy import text

from src.core.config import settings

# ======================== DATA MODELS ========================

@dataclass
class DownloadResult:
    """Result of a download operation with all metadata."""
    content: str
    content_hash: str
    size_bytes: int
    download_time_ms: int
    url: str
    success: bool
    error_message: Optional[str] = None

# ======================== DOWNLOAD MANAGER CLASS ========================

class DownloadManager:
    """
    Handles content retrieval with optimization and error handling.
    
    Features:
    - Content hashing for change detection
    - Request optimization with sessions
    - Comprehensive error handling
    - Performance monitoring
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """Create optimized HTTP session."""
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'TrustCheck-Compliance-Platform/1.0 (sanctions-monitoring)',
            'Accept': 'application/xml, text/xml, text/csv, application/json, */*',
            'Accept-Encoding': 'gzip, deflate',
            'Accept-Language': 'en-US,en;q=0.9'
        })
        return session
    
    # ======================== MAIN DOWNLOAD METHOD ========================
    
    def download_content(self, url: str, timeout: int = 120) -> DownloadResult:
        """
        Download content with comprehensive error handling.
        
        Args:
            url: URL to download from
            timeout: Request timeout in seconds
            
        Returns:
            DownloadResult with content and metadata
        """
        start_time = datetime.now()
        
        try:
            self.logger.info(f"Downloading content from: {url}")
            
            # Make HTTP request
            response = self.session.get(
                url,
                timeout=timeout,
                stream=True,
                allow_redirects=True
            )
            response.raise_for_status()
            
            # Get content
            content = response.text
            
            # Validate content size
            if len(content) < 1000:  # Suspiciously small for sanctions data
                raise ValueError(f"Content too small: {len(content)} bytes")
            
            # Calculate metrics
            size_bytes = len(content.encode('utf-8'))
            download_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            content_hash = self._calculate_hash(content)
            
            self.logger.info(
                f"Downloaded {size_bytes:,} bytes in {download_time_ms}ms "
                f"(hash: {content_hash[:12]}...)"
            )
            
            return DownloadResult(
                content=content,
                content_hash=content_hash,
                size_bytes=size_bytes,
                download_time_ms=download_time_ms,
                url=url,
                success=True
            )
            
        except requests.exceptions.RequestException as e:
            return self._create_error_result(url, start_time, f"Network error: {e}")
        except ValueError as e:
            return self._create_error_result(url, start_time, f"Validation error: {e}")
        except Exception as e:
            return self._create_error_result(url, start_time, f"Unexpected error: {e}")
    
    # ======================== CHANGE DETECTION SUPPORT ========================
    
    def should_skip_processing(self, content_hash: str, source: str) -> bool:
        """
        Check if content hash matches previous run (skip if unchanged).
        
        Args:
            content_hash: SHA-256 hash of current content
            source: Source name (e.g., 'us_ofac')
            
        Returns:
            True if content unchanged, False if should process
        """
        try:
            from src.database.connection import db_manager
            
            with db_manager.get_session() as db:
                # Query for last successful content hash
                last_run = db.execute(
                    text("""
                        SELECT content_hash 
                        FROM scraper_runs 
                        WHERE source = :source 
                        AND status = 'SUCCESS' 
                        AND content_hash IS NOT NULL
                        ORDER BY started_at DESC 
                        LIMIT 1
                    """),
                    {'source': source}
                ).fetchone()
                
                if last_run and last_run.content_hash == content_hash:
                    self.logger.info(f"Content unchanged for {source}, skipping processing")
                    return True
                
                self.logger.info(f"Content changed for {source}, proceeding with processing")
                return False
                
        except Exception as e:
            self.logger.warning(f"Could not check previous content hash: {e}")
            return False  # Process anyway if unsure
    
    # ======================== HELPER METHODS ========================
    
    def _calculate_hash(self, content: str) -> str:
        """Calculate SHA-256 hash of content."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def _create_error_result(self, url: str, start_time: datetime, error_msg: str) -> DownloadResult:
        """Create error result with timing information."""
        self.logger.error(error_msg)
        
        download_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        
        return DownloadResult(
            content="",
            content_hash="",
            size_bytes=0,
            download_time_ms=download_time_ms,
            url=url,
            success=False,
            error_message=error_msg
        )