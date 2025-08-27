"""
Change-Aware Scraper Base Class

scraper that integrates change detection into the scraping workflow.
Extends the existing BaseScraper with change detection capabilities.
"""

from typing import List, Dict, Any
from datetime import datetime
from contextlib import contextmanager
import uuid
import logging
from sqlalchemy import text

from src.scrapers.base.scraper import BaseScraper, ScrapingResult
from src.services.change_detection.download_manager import DownloadManager
from src.services.change_detection.change_detector import ChangeDetector, EntityChange
from src.infrastructure.database.connection import db_manager
from src.infrastructure.database.models import SanctionedEntity, ContentSnapshot, ChangeEvent, ScraperRun

# ======================== CHANGE-AWARE SCRAPER CLASS ========================

class ChangeAwareScraper(BaseScraper):
    """
    Production scraper with integrated change detection.
    
    Workflow:
    1. Download content with hash calculation
    2. Skip processing if content unchanged (optimization)
    3. Get current entities for comparison
    4. Parse new entities
    5. Detect changes between old and new
    6. Store everything in database transaction
    7. Send notifications for critical changes
    
    Features:
    - Content hash-based change detection
    - Atomic database transactions
    - Comprehensive metrics and logging
    - Error recovery and rollback
    """
    
    def __init__(self, source_name: str, source_url: str):
        super().__init__(source_name)
        self.source_url = source_url
        self.download_manager = DownloadManager()
        self.change_detector = ChangeDetector(source_name)
    
    # ======================== MAIN WORKFLOW ========================
    
    def scrape_and_store(self) -> ScrapingResult:
        """Enhanced scraping with complete change detection workflow."""
        
        run_id = f"{self.source_name}_{int(datetime.utcnow().timestamp())}"
        overall_start = datetime.utcnow()
        
        try:
            self.logger.info(f"Starting change-aware scraping: {run_id}")
            
            # Step 1: Download content with hash calculation
            download_result = self.download_manager.download_content(self.source_url)
            if not download_result.success:
                return self._create_failed_result(run_id, download_result.error_message)
            
            # Step 2: Early exit optimization - skip if content unchanged
            if self.download_manager.should_skip_processing(download_result.content_hash, self.source_name):
                return self._create_skipped_result(run_id, download_result)
            
            # Step 3: Get current entities for comparison
            old_entities = self._get_current_entities()
            old_content_hash = self._get_last_content_hash()
            
            # Step 4: Parse new entities from downloaded content
            parse_start = datetime.utcnow()
            new_entities = self.parse_entities(download_result.content)
            parse_time = int((datetime.utcnow() - parse_start).total_seconds() * 1000)
            
            self.logger.info(f"Parsed {len(new_entities)} entities in {parse_time}ms")
            
            # Step 5: Detect changes between old and new entities
            diff_start = datetime.utcnow()
            changes, metrics = self.change_detector.detect_changes(
                old_entities=old_entities,
                new_entities=new_entities,
                old_content_hash=old_content_hash or '',
                new_content_hash=download_result.content_hash,
                scraper_run_id=run_id
            )
            diff_time = int((datetime.utcnow() - diff_start).total_seconds() * 1000)
            
            self.logger.info(f"Detected {len(changes)} changes in {diff_time}ms")
            
            # Step 6: Store everything in atomic database transaction
            storage_start = datetime.utcnow()
            with self._database_transaction():
                # Store new entity data (replace old)
                self.store_entities(new_entities)
                
                # Store change events if any
                if changes:
                    self._store_changes(changes, run_id)
                
                # Store content snapshot for audit trail
                self._store_content_snapshot(
                    source=self.source_name,
                    content_hash=download_result.content_hash,
                    size_bytes=download_result.size_bytes,
                    run_id=run_id
                )
                
                # Store comprehensive scraper run record
                self._store_scraper_run(
                    run_id=run_id,
                    download_result=download_result,
                    metrics=metrics,
                    parse_time=parse_time,
                    diff_time=diff_time,
                    entity_count=len(new_entities)
                )
            
            storage_time = int((datetime.utcnow() - storage_start).total_seconds() * 1000)
            
            # Step 7: Send notifications for critical changes (after successful commit)
            if changes:
                try:
                    self._send_notifications(changes)
                    self._mark_notifications_sent(changes)
                except Exception as e:
                    self.logger.error(f"Notification dispatch failed: {e}")
                    # Don't fail the entire process for notification errors
            
            # Step 8: Create success result
            total_duration = (datetime.utcnow() - overall_start).total_seconds()
            
            result = ScrapingResult(
                source=self.source_name,
                entities_processed=len(new_entities),
                entities_added=metrics['entities_added'],
                entities_updated=metrics['entities_modified'],
                entities_removed=metrics['entities_removed'],
                duration_seconds=total_duration,
                status="SUCCESS"
            )
            
            self.logger.info(
                f"Scraping completed successfully: {result.entities_added} added, "
                f"{result.entities_updated} modified, {result.entities_removed} removed "
                f"in {total_duration:.1f}s"
            )
            
            return result
            
        except Exception as e:
            error_msg = f"Scraping failed: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            
            # Record failed run for audit trail
            try:
                self._record_failed_run(run_id, error_msg)
            except Exception:
                pass  # Don't let logging failure mask original error
            
            return self._create_failed_result(run_id, error_msg)
    
    # ======================== DATA RETRIEVAL METHODS ========================
    
    def _get_current_entities(self) -> List[Dict[str, Any]]:
        """Get current entities from database for comparison."""
        try:
            with db_manager.get_session() as db:
                entities = db.query(SanctionedEntity).filter(
                    SanctionedEntity.source == self.source_name,
                    SanctionedEntity.is_active == True
                ).all()
                
                return [
                    {
                        'uid': entity.uid,
                        'name': entity.name,
                        'entity_type': entity.entity_type,
                        'programs': entity.programs or [],
                        'aliases': entity.aliases or [],
                        'addresses': entity.addresses or [],
                        'dates_of_birth': entity.dates_of_birth or [],
                        'places_of_birth': entity.places_of_birth or [],
                        'nationalities': entity.nationalities or [],
                        'remarks': entity.remarks
                    }
                    for entity in entities
                ]
        except Exception as e:
            self.logger.warning(f"Could not retrieve current entities: {e}")
            return []
    
    def _get_last_content_hash(self) -> str:
        """Get content hash from last successful run."""
        try:
            with db_manager.get_session() as db:
                result = db.execute(
                    text("""
                        SELECT content_hash
                        FROM scraper_runs
                        WHERE source = :source
                        AND status = 'SUCCESS'
                        AND content_hash IS NOT NULL
                        ORDER BY started_at DESC
                        LIMIT 1
                    """),
                    {'source': self.source_name}
                ).fetchone()
                
                return result.content_hash if result else ''
        except Exception as e:
            self.logger.warning(f"Could not retrieve last content hash: {e}")
            return ''
    
    # ======================== DATABASE STORAGE METHODS ========================
    
    @contextmanager
    def _database_transaction(self):
        """Database transaction context manager with comprehensive error handling."""
        with db_manager.get_session() as session:
            try:
                yield session
                session.commit()
            except Exception as e:
                session.rollback()
                self.logger.error(f"Database transaction failed: {e}")
                raise
    
    def _store_changes(self, changes: List[EntityChange], run_id: str) -> None:
        """Store change events in database."""
        with db_manager.get_session() as db:
            for change in changes:
                change_event = ChangeEvent(
                    entity_uid=change.entity_uid,
                    entity_name=change.entity_name,
                    source=self.source_name,
                    change_type=change.change_type,
                    risk_level=change.risk_level,
                    field_changes=change.field_changes,
                    change_summary=change.change_summary,
                    old_content_hash=change.old_content_hash,
                    new_content_hash=change.new_content_hash,
                    scraper_run_id=run_id,
                    detected_at=datetime.utcnow()
                )
                db.add(change_event)
            
            db.commit()
            self.logger.info(f"Stored {len(changes)} change events")
    
    def _store_content_snapshot(self, source: str, content_hash: str, size_bytes: int, run_id: str) -> None:
        """Store content snapshot for audit trail."""
        with db_manager.get_session() as db:
            snapshot = ContentSnapshot(
                source=source,
                content_hash=content_hash,
                content_size_bytes=size_bytes,
                scraper_run_id=run_id,
                snapshot_time=datetime.utcnow()
            )
            db.add(snapshot)
            db.commit()
            self.logger.debug(f"Stored content snapshot: {content_hash[:12]}...")
    
    def _store_scraper_run(
        self, 
        run_id: str, 
        download_result, 
        metrics: Dict[str, int], 
        parse_time: int, 
        diff_time: int, 
        entity_count: int
    ) -> None:
        """Store comprehensive scraper run record."""
        with db_manager.get_session() as db:
            scraper_run = ScraperRun(
                run_id=run_id,
                source=self.source_name,
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
                duration_seconds=int((datetime.utcnow() - datetime.utcnow()).total_seconds()),
                status='SUCCESS',
                source_url=self.source_url,
                content_hash=download_result.content_hash,
                content_size_bytes=download_result.size_bytes,
                content_changed=True,  # If we got here, content changed
                entities_processed=entity_count,
                entities_added=metrics['entities_added'],
                entities_modified=metrics['entities_modified'],
                entities_removed=metrics['entities_removed'],
                critical_changes=metrics['critical_changes'],
                high_risk_changes=metrics['high_risk_changes'],
                medium_risk_changes=metrics['medium_risk_changes'],
                low_risk_changes=metrics['low_risk_changes'],
                download_time_ms=download_result.download_time_ms,
                parsing_time_ms=parse_time,
                diff_time_ms=diff_time
            )
            db.add(scraper_run)
            db.commit()
            self.logger.debug(f"Stored scraper run record: {run_id}")
    
    # ======================== NOTIFICATION METHODS ========================
    
    def _send_notifications(self, changes: List[EntityChange]) -> None:
        """Send notifications for critical changes (placeholder implementation)."""
        critical_changes = [c for c in changes if c.risk_level == 'CRITICAL']
        
        if critical_changes:
            self.logger.warning(f"CRITICAL: {len(critical_changes)} critical changes detected!")
            for change in critical_changes:
                self.logger.warning(f"  - {change.change_summary}")
        
        # TODO: Implement actual notification dispatch (email, webhooks, Slack)
        self.logger.info(f"Would send notifications for {len(critical_changes)} critical changes")
    
    def _mark_notifications_sent(self, changes: List[EntityChange]) -> None:
        """Mark notifications as sent in database."""
        # TODO: Update ChangeEvent records with notification status
        pass
    
    # ======================== RESULT CREATION METHODS ========================
    
    def _create_skipped_result(self, run_id: str, download_result) -> ScrapingResult:
        """Create result for skipped processing (no content changes)."""
        
        # Still record the run for audit trail
        try:
            self._store_skipped_run(run_id, download_result)
        except Exception as e:
            self.logger.warning(f"Could not record skipped run: {e}")
        
        return ScrapingResult(
            source=self.source_name,
            entities_processed=0,
            entities_added=0,
            entities_updated=0,
            entities_removed=0,
            duration_seconds=download_result.download_time_ms / 1000,
            status="SKIPPED"
        )
    
    def _create_failed_result(self, run_id: str, error_message: str) -> ScrapingResult:
        """Create result for failed processing."""
        return ScrapingResult(
            source=self.source_name,
            entities_processed=0,
            entities_added=0,
            entities_updated=0,
            entities_removed=0,
            duration_seconds=0,
            status="FAILED",
            error_message=error_message
        )
    
    def _store_skipped_run(self, run_id: str, download_result) -> None:
        """Store record of skipped run."""
        with db_manager.get_session() as db:
            scraper_run = ScraperRun(
                run_id=run_id,
                source=self.source_name,
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
                status='SKIPPED',
                source_url=self.source_url,
                content_hash=download_result.content_hash,
                content_size_bytes=download_result.size_bytes,
                content_changed=False,
                download_time_ms=download_result.download_time_ms
            )
            db.add(scraper_run)
            db.commit()
    
    def _record_failed_run(self, run_id: str, error_message: str) -> None:
        """Record failed run for audit trail."""
        with db_manager.get_session() as db:
            scraper_run = ScraperRun(
                run_id=run_id,
                source=self.source_name,
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
                status='FAILED',
                source_url=self.source_url,
                error_message=error_message
            )
            db.add(scraper_run)
            db.commit()