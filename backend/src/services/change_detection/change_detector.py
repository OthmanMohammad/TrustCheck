"""
Change Detector Service

Core change detection logic that compares old vs new entities
and identifies additions, modifications, and removals.
"""

from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging

# ======================== DATA MODELS ========================

@dataclass
class EntityChange:
    """Represents a detected change in an entity."""
    entity_uid: str
    entity_name: str
    change_type: str  # ADDED, REMOVED, MODIFIED
    risk_level: str   # CRITICAL, HIGH, MEDIUM, LOW
    field_changes: List[Dict[str, Any]]  # [{field_name, old_value, new_value, change_type}]
    change_summary: str
    old_content_hash: str = None
    new_content_hash: str = None

# ======================== CHANGE DETECTOR CLASS ========================

class ChangeDetector:
    """
    change detection with comprehensive logging.
    
    Features:
    - Entity-level change detection (added/removed/modified)
    - Field-level change analysis
    - Risk classification based on field importance
    - Human-readable change summaries
    - Performance metrics
    """
    
    def __init__(self, source: str):
        self.source = source
        self.logger = logging.getLogger(f"change_detector.{source}")
        
        # Field importance classification for risk assessment
        self.critical_fields = {'name', 'programs', 'entity_type'}
        self.high_risk_fields = {'addresses', 'aliases', 'nationalities'}
        self.medium_risk_fields = {'dates_of_birth', 'places_of_birth', 'remarks'}
        
        # Fields to track for changes
        self.tracked_fields = {
            'name', 'entity_type', 'programs', 'aliases', 'addresses',
            'dates_of_birth', 'places_of_birth', 'nationalities', 'remarks'
        }
    
    # ======================== MAIN DETECTION METHOD ========================
    
    def detect_changes(
        self,
        old_entities: List[Dict[str, Any]],
        new_entities: List[Dict[str, Any]],
        old_content_hash: str,
        new_content_hash: str,
        scraper_run_id: str
    ) -> Tuple[List[EntityChange], Dict[str, int]]:
        """
        Main change detection with comprehensive metrics.
        
        Args:
            old_entities: Previous entity data
            new_entities: Current entity data
            old_content_hash: Hash of previous content
            new_content_hash: Hash of current content
            scraper_run_id: Unique ID for this scraper run
            
        Returns:
            Tuple of (changes_list, metrics_dict)
        """
        start_time = datetime.utcnow()
        self.logger.info(
            f"Detecting changes: {len(old_entities)} -> {len(new_entities)} entities"
        )
        
        # Build entity lookup maps for efficient comparison
        old_entities_map = {e['uid']: e for e in old_entities if e.get('uid')}
        new_entities_map = {e['uid']: e for e in new_entities if e.get('uid')}
        
        old_uids = set(old_entities_map.keys())
        new_uids = set(new_entities_map.keys())
        
        changes = []
        
        # Detect additions
        added_uids = new_uids - old_uids
        self.logger.info(f"Found {len(added_uids)} new entities")
        for uid in added_uids:
            change = self._create_addition_change(
                uid, new_entities_map[uid], new_content_hash, scraper_run_id
            )
            changes.append(change)
        
        # Detect removals
        removed_uids = old_uids - new_uids
        self.logger.info(f"Found {len(removed_uids)} removed entities")
        for uid in removed_uids:
            change = self._create_removal_change(
                uid, old_entities_map[uid], old_content_hash, scraper_run_id
            )
            changes.append(change)
        
        # Detect modifications
        common_uids = old_uids & new_uids
        self.logger.info(f"Comparing {len(common_uids)} common entities for modifications")
        modifications = 0
        
        for uid in common_uids:
            old_entity = old_entities_map[uid]
            new_entity = new_entities_map[uid]
            
            field_changes = self._compare_entities(old_entity, new_entity)
            if field_changes:
                change = self._create_modification_change(
                    uid, old_entity, new_entity, field_changes,
                    old_content_hash, new_content_hash, scraper_run_id
                )
                changes.append(change)
                modifications += 1
        
        # Calculate metrics
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        metrics = {
            'processing_time_ms': int(processing_time * 1000),
            'entities_added': len(added_uids),
            'entities_modified': modifications,
            'entities_removed': len(removed_uids),
            'critical_changes': len([c for c in changes if c.risk_level == 'CRITICAL']),
            'high_risk_changes': len([c for c in changes if c.risk_level == 'HIGH']),
            'medium_risk_changes': len([c for c in changes if c.risk_level == 'MEDIUM']),
            'low_risk_changes': len([c for c in changes if c.risk_level == 'LOW'])
        }
        
        self.logger.info(
            f"Change detection completed in {processing_time:.1f}s: "
            f"{metrics['entities_added']} added, {metrics['entities_modified']} modified, "
            f"{metrics['entities_removed']} removed"
        )
        
        return changes, metrics
    
    # ======================== ENTITY COMPARISON METHODS ========================
    
    def _compare_entities(self, old_entity: Dict[str, Any], new_entity: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Compare two entities field by field to detect changes.
        
        Args:
            old_entity: Previous entity state
            new_entity: Current entity state
            
        Returns:
            List of field changes
        """
        changes = []
        
        for field in self.tracked_fields:
            old_value = old_entity.get(field)
            new_value = new_entity.get(field)
            
            if self._values_differ(old_value, new_value):
                changes.append({
                    'field_name': field,
                    'old_value': old_value,
                    'new_value': new_value,
                    'change_type': self._classify_change_type(old_value, new_value)
                })
        
        return changes
    
    def _values_differ(self, old_value: Any, new_value: Any) -> bool:
        """
        Determine if values represent meaningful difference.
        Handles None values, lists, and strings appropriately.
        """
        # Handle None cases
        if old_value is None and new_value is None:
            return False
        if old_value is None or new_value is None:
            return True
        
        # Handle lists (common for aliases, addresses, programs)
        if isinstance(old_value, list) and isinstance(new_value, list):
            # Normalize and compare as sets (order doesn't matter)
            old_set = set(str(item).strip() for item in old_value if item)
            new_set = set(str(item).strip() for item in new_value if item)
            return old_set != new_set
        
        # Handle strings (normalize whitespace)
        if isinstance(old_value, str) and isinstance(new_value, str):
            return old_value.strip() != new_value.strip()
        
        # Default comparison
        return old_value != new_value
    
    def _classify_change_type(self, old_value: Any, new_value: Any) -> str:
        """Classify the type of field change."""
        if old_value is None:
            return 'field_added'
        elif new_value is None:
            return 'field_removed'
        else:
            return 'field_modified'
    
    # ======================== CHANGE CREATION METHODS ========================
    
    def _create_addition_change(
        self, uid: str, entity: Dict[str, Any], content_hash: str, run_id: str
    ) -> EntityChange:
        """Create change record for new entity."""
        
        # Assess addition risk based on entity properties
        programs = entity.get('programs', [])
        high_risk_programs = {'SDGT', 'TERRORISM', 'PROLIFERATION', 'CYBER'}
        
        if any(prog in high_risk_programs for prog in programs):
            risk_level = 'CRITICAL'
        elif entity.get('entity_type') == 'PERSON':
            risk_level = 'HIGH'
        else:
            risk_level = 'MEDIUM'
        
        return EntityChange(
            entity_uid=uid,
            entity_name=entity.get('name', 'Unknown'),
            change_type='ADDED',
            risk_level=risk_level,
            field_changes=[],
            change_summary=f"New {entity.get('entity_type', 'entity').lower()} added: {entity.get('name')}",
            new_content_hash=content_hash
        )
    
    def _create_removal_change(
        self, uid: str, entity: Dict[str, Any], content_hash: str, run_id: str
    ) -> EntityChange:
        """Create change record for removed entity."""
        
        return EntityChange(
            entity_uid=uid,
            entity_name=entity.get('name', 'Unknown'),
            change_type='REMOVED',
            risk_level='CRITICAL',  # Removals always critical for compliance
            field_changes=[],
            change_summary=f"Entity removed from sanctions list: {entity.get('name')}",
            old_content_hash=content_hash
        )
    
    def _create_modification_change(
        self,
        uid: str,
        old_entity: Dict[str, Any],
        new_entity: Dict[str, Any],
        field_changes: List[Dict[str, Any]],
        old_hash: str,
        new_hash: str,
        run_id: str
    ) -> EntityChange:
        """Create change record for modified entity."""
        
        # Assess risk level based on changed fields
        risk_level = self._assess_risk_level(field_changes, new_entity.get('entity_type'))
        
        # Generate human-readable summary
        changed_field_names = [fc['field_name'] for fc in field_changes]
        change_summary = f"Modified {new_entity.get('name')}: updated {', '.join(changed_field_names)}"
        
        return EntityChange(
            entity_uid=uid,
            entity_name=new_entity.get('name', 'Unknown'),
            change_type='MODIFIED',
            risk_level=risk_level,
            field_changes=field_changes,
            change_summary=change_summary,
            old_content_hash=old_hash,
            new_content_hash=new_hash
        )
    
    # ======================== RISK ASSESSMENT ========================
    
    def _assess_risk_level(self, field_changes: List[Dict[str, Any]], entity_type: str = None) -> str:
        """
        Assess overall risk level of changes based on field importance.
        
        Args:
            field_changes: List of field changes
            entity_type: Type of entity (for context)
            
        Returns:
            Risk level: CRITICAL, HIGH, MEDIUM, or LOW
        """
        changed_fields = {change['field_name'] for change in field_changes}
        
        # Critical: Core identification fields changed
        if any(field in self.critical_fields for field in changed_fields):
            return 'CRITICAL'
        
        # High: Important fields changed
        if any(field in self.high_risk_fields for field in changed_fields):
            return 'HIGH'
        
        # Medium: Multiple changes or medium-risk fields
        if len(field_changes) >= 3 or any(field in self.medium_risk_fields for field in changed_fields):
            return 'MEDIUM'
        
        return 'LOW'