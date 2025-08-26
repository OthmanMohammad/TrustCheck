"""
Sanctioned Entity Domain Model

Business logic and domain rules for sanctioned entities.
"""

from typing import List, Optional, Dict, Any, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import hashlib

from src.core.enums import EntityType, SanctionsSource, RiskLevel
from src.core.exceptions import ValidationError, EntityValidationError
from src.utils.logging import get_logger


# ======================== VALUE OBJECTS ========================

@dataclass(frozen=True)
class EntityId:
    """Entity identifier value object."""
    source: SanctionsSource
    uid: str
    
    def __post_init__(self):
        if not self.uid or not self.uid.strip():
            raise ValidationError("Entity UID cannot be empty")
        
        # Validate UID format based on source
        self._validate_uid_format()
    
    def _validate_uid_format(self) -> None:
        """Validate UID format based on source."""
        uid = self.uid.strip().upper()
        
        if self.source == SanctionsSource.US_OFAC:
            if not uid.isdigit():
                raise ValidationError(f"OFAC UID must be numeric: {uid}")
        elif self.source == SanctionsSource.UN_CONSOLIDATED:
            if not (uid.startswith('IND.') or uid.startswith('ENT.')):
                raise ValidationError(f"UN UID must start with IND. or ENT.: {uid}")
    
    def __str__(self) -> str:
        return f"{self.source.value}:{self.uid}"


@dataclass(frozen=True)
class ContentHash:
    """Content hash value object for change detection."""
    hash_value: str
    algorithm: str = "SHA-256"
    
    def __post_init__(self):
        if not self.hash_value or len(self.hash_value) != 64:
            raise ValidationError("Content hash must be 64 character SHA-256 hex")
        
        if not all(c in '0123456789abcdef' for c in self.hash_value.lower()):
            raise ValidationError("Content hash must be valid hexadecimal")
    
    @classmethod
    def from_content(cls, content: str) -> 'ContentHash':
        """Generate hash from content."""
        hash_value = hashlib.sha256(content.encode('utf-8')).hexdigest()
        return cls(hash_value=hash_value)
    
    def __str__(self) -> str:
        return f"{self.hash_value[:12]}..."


# ======================== DOMAIN ENTITIES ========================

@dataclass
class SanctionedEntity:
    """
    Sanctioned Entity Domain Model
    
    Contains business logic and domain rules for sanctioned entities.
    Validates data integrity and business rules.
    """
    
    # Identity
    entity_id: EntityId
    name: str
    entity_type: EntityType
    
    # Sanctions Information
    programs: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)
    addresses: List[str] = field(default_factory=list)
    
    # Personal Information (for persons)
    dates_of_birth: List[str] = field(default_factory=list)
    places_of_birth: List[str] = field(default_factory=list)
    nationalities: List[str] = field(default_factory=list)
    
    # Additional Information
    remarks: Optional[str] = None
    
    # Metadata
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    content_hash: Optional[ContentHash] = None
    
    # Business Logic Fields
    _risk_score: Optional[float] = field(default=None, init=False)
    _logger = field(default_factory=lambda: get_logger("domain.sanctioned_entity"), init=False)
    
    def __post_init__(self):
        """Post-initialization validation and processing."""
        self._validate_entity()
        self._normalize_data()
        self._calculate_content_hash()
    
    # ======================== VALIDATION METHODS ========================
    
    def _validate_entity(self) -> None:
        """Validate entity business rules."""
        errors = {}
        
        # Name validation
        if not self.name or not self.name.strip():
            errors['name'] = ["Entity name is required"]
        elif len(self.name.strip()) > 500:
            errors['name'] = ["Entity name cannot exceed 500 characters"]
        
        # Entity type specific validation
        if self.entity_type == EntityType.PERSON:
            self._validate_person_fields(errors)
        elif self.entity_type == EntityType.VESSEL:
            self._validate_vessel_fields(errors)
        elif self.entity_type == EntityType.AIRCRAFT:
            self._validate_aircraft_fields(errors)
        
        # Programs validation
        if not self.programs:
            errors['programs'] = ["At least one sanctions program is required"]
        
        # Dates validation
        self._validate_dates(errors)
        
        if errors:
            raise EntityValidationError(
                entity_type=self.entity_type.value,
                field_errors=errors
            )
    
    def _validate_person_fields(self, errors: Dict[str, List[str]]) -> None:
        """Validate person-specific fields."""
        # Birth dates should only exist for persons
        if self.entity_type != EntityType.PERSON and self.dates_of_birth:
            errors['dates_of_birth'] = ["Birth dates only allowed for persons"]
        
        # Persons should ideally have nationality
        if self.entity_type == EntityType.PERSON and not self.nationalities:
            self._logger.warning(f"Person {self.name} has no nationality information")
    
    def _validate_vessel_fields(self, errors: Dict[str, List[str]]) -> None:
        """Validate vessel-specific fields."""
        # Vessels shouldn't have birth information
        if self.dates_of_birth or self.places_of_birth:
            errors['birth_info'] = ["Vessels cannot have birth information"]
    
    def _validate_aircraft_fields(self, errors: Dict[str, List[str]]) -> None:
        """Validate aircraft-specific fields.""" 
        # Aircraft shouldn't have birth information
        if self.dates_of_birth or self.places_of_birth:
            errors['birth_info'] = ["Aircraft cannot have birth information"]
    
    def _validate_dates(self, errors: Dict[str, List[str]]) -> None:
        """Validate date formats."""
        from datetime import datetime
        
        for i, date_str in enumerate(self.dates_of_birth):
            if date_str and not self._is_valid_date_format(date_str):
                if 'dates_of_birth' not in errors:
                    errors['dates_of_birth'] = []
                errors['dates_of_birth'].append(f"Invalid date format at index {i}: {date_str}")
    
    def _is_valid_date_format(self, date_str: str) -> bool:
        """Check if date string is in valid format."""
        common_formats = [
            '%Y-%m-%d',      # 1980-01-01
            '%d/%m/%Y',      # 01/01/1980
            '%m/%d/%Y',      # 01/01/1980
            '%Y',            # 1980 (year only)
            '%b %Y',         # Jan 1980
            '%B %Y',         # January 1980
        ]
        
        for fmt in common_formats:
            try:
                datetime.strptime(date_str.strip(), fmt)
                return True
            except ValueError:
                continue
        
        return False
    
    # ======================== DATA NORMALIZATION ========================
    
    def _normalize_data(self) -> None:
        """Normalize and clean entity data."""
        # Normalize name
        self.name = self.name.strip()
        
        # Normalize and deduplicate lists
        self.programs = self._normalize_list(self.programs)
        self.aliases = self._normalize_list(self.aliases)
        self.addresses = self._normalize_list(self.addresses) 
        self.dates_of_birth = self._normalize_list(self.dates_of_birth)
        self.places_of_birth = self._normalize_list(self.places_of_birth)
        self.nationalities = self._normalize_list(self.nationalities)
        
        # Normalize remarks
        if self.remarks:
            self.remarks = self.remarks.strip()
            if not self.remarks:
                self.remarks = None
    
    def _normalize_list(self, items: List[str]) -> List[str]:
        """Normalize and deduplicate list of strings."""
        if not items:
            return []
        
        # Remove empty strings, strip whitespace, and deduplicate while preserving order
        normalized = []
        seen = set()
        
        for item in items:
            if item and isinstance(item, str):
                cleaned = item.strip()
                if cleaned and cleaned.upper() not in seen:
                    normalized.append(cleaned)
                    seen.add(cleaned.upper())
        
        return normalized
    
    # ======================== BUSINESS LOGIC METHODS ========================
    
    def calculate_risk_score(self) -> float:
        """
        Calculate entity risk score based on various factors.
        
        Returns:
            Risk score between 0.0 and 1.0
        """
        if self._risk_score is not None:
            return self._risk_score
        
        score = 0.0
        
        # Program risk weights
        high_risk_programs = {
            'SDGT', 'TERRORISM', 'PROLIFERATION', 'CYBER', 'SYRIA', 'IRAN',
            'NORTH_KOREA', 'UKRAINE', 'BELARUS'
        }
        
        program_risk = sum(0.3 for program in self.programs if program in high_risk_programs)
        score += min(program_risk, 0.4)  # Max 0.4 from programs
        
        # Entity type risk
        type_risks = {
            EntityType.PERSON: 0.2,
            EntityType.COMPANY: 0.15,
            EntityType.VESSEL: 0.1,
            EntityType.AIRCRAFT: 0.1,
            EntityType.OTHER: 0.05
        }
        score += type_risks.get(self.entity_type, 0.05)
        
        # Complexity risk (more aliases/addresses = higher risk)
        complexity_score = (len(self.aliases) * 0.02) + (len(self.addresses) * 0.02)
        score += min(complexity_score, 0.2)  # Max 0.2 from complexity
        
        # Recency risk (recently added = higher risk)
        if self.created_at:
            days_since_creation = (datetime.utcnow() - self.created_at).days
            if days_since_creation < 30:
                score += 0.1  # Recent additions are higher risk
        
        # Cap at 1.0
        self._risk_score = min(score, 1.0)
        return self._risk_score
    
    def get_risk_level(self) -> RiskLevel:
        """Get categorical risk level."""
        score = self.calculate_risk_score()
        
        if score >= 0.8:
            return RiskLevel.CRITICAL
        elif score >= 0.6:
            return RiskLevel.HIGH
        elif score >= 0.3:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    def has_program(self, program: str) -> bool:
        """Check if entity is on specific sanctions program."""
        return program.upper() in [p.upper() for p in self.programs]
    
    def has_any_programs(self, programs: List[str]) -> bool:
        """Check if entity is on any of the specified programs."""
        entity_programs = {p.upper() for p in self.programs}
        check_programs = {p.upper() for p in programs}
        return bool(entity_programs & check_programs)
    
    def get_primary_nationality(self) -> Optional[str]:
        """Get primary nationality (first one listed)."""
        return self.nationalities[0] if self.nationalities else None
    
    def is_person(self) -> bool:
        """Check if entity is a person."""
        return self.entity_type == EntityType.PERSON
    
    def is_company(self) -> bool:
        """Check if entity is a company."""
        return self.entity_type == EntityType.COMPANY
    
    def has_aliases(self) -> bool:
        """Check if entity has any aliases."""
        return len(self.aliases) > 0
    
    def get_all_names(self) -> List[str]:
        """Get all names (primary name + aliases)."""
        names = [self.name]
        names.extend(self.aliases)
        return names
    
    # ======================== CHANGE DETECTION METHODS ========================
    
    def _calculate_content_hash(self) -> None:
        """Calculate content hash for change detection."""
        content_parts = [
            self.name,
            self.entity_type.value,
            '|'.join(sorted(self.programs)),
            '|'.join(sorted(self.aliases)),
            '|'.join(sorted(self.addresses)),
            '|'.join(sorted(self.dates_of_birth)),
            '|'.join(sorted(self.places_of_birth)),
            '|'.join(sorted(self.nationalities)),
            self.remarks or ''
        ]
        
        content = '||'.join(content_parts)
        self.content_hash = ContentHash.from_content(content)
    
    def has_changed(self, other: 'SanctionedEntity') -> bool:
        """Check if entity has changed compared to another version."""
        if not self.content_hash or not other.content_hash:
            return True  # Assume changed if hash missing
        
        return self.content_hash.hash_value != other.content_hash.hash_value
    
    def get_field_changes(self, other: 'SanctionedEntity') -> List[Dict[str, Any]]:
        """Get detailed field changes compared to another version."""
        changes = []
        
        # Compare simple fields
        simple_fields = ['name', 'entity_type', 'remarks']
        for field in simple_fields:
            old_value = getattr(other, field, None)
            new_value = getattr(self, field, None)
            
            if old_value != new_value:
                changes.append({
                    'field_name': field,
                    'old_value': old_value,
                    'new_value': new_value,
                    'change_type': 'field_modified'
                })
        
        # Compare list fields
        list_fields = ['programs', 'aliases', 'addresses', 'dates_of_birth', 'places_of_birth', 'nationalities']
        for field in list_fields:
            old_list = set(getattr(other, field, []))
            new_list = set(getattr(self, field, []))
            
            added = new_list - old_list
            removed = old_list - new_list
            
            if added:
                changes.append({
                    'field_name': field,
                    'old_value': list(old_list),
                    'new_value': list(new_list),
                    'change_type': 'list_items_added',
                    'added_items': list(added)
                })
            
            if removed:
                changes.append({
                    'field_name': field,
                    'old_value': list(old_list),
                    'new_value': list(new_list),
                    'change_type': 'list_items_removed',
                    'removed_items': list(removed)
                })
        
        return changes
    
    # ======================== COMPARISON METHODS ========================
    
    def similarity_score(self, other: 'SanctionedEntity') -> float:
        """Calculate similarity score with another entity (0.0 to 1.0)."""
        if not other:
            return 0.0
        
        score = 0.0
        total_weight = 0.0
        
        # Name similarity (weight: 0.4)
        name_similarity = self._string_similarity(self.name, other.name)
        score += name_similarity * 0.4
        total_weight += 0.4
        
        # Entity type match (weight: 0.2)
        if self.entity_type == other.entity_type:
            score += 0.2
        total_weight += 0.2
        
        # Program overlap (weight: 0.2)
        if self.programs and other.programs:
            program_overlap = len(set(self.programs) & set(other.programs))
            program_union = len(set(self.programs) | set(other.programs))
            program_similarity = program_overlap / program_union if program_union > 0 else 0
            score += program_similarity * 0.2
        total_weight += 0.2
        
        # Nationality overlap (weight: 0.1)
        if self.nationalities and other.nationalities:
            nat_overlap = len(set(self.nationalities) & set(other.nationalities))
            nat_union = len(set(self.nationalities) | set(other.nationalities))
            nat_similarity = nat_overlap / nat_union if nat_union > 0 else 0
            score += nat_similarity * 0.1
        total_weight += 0.1
        
        # Alias similarity (weight: 0.1)
        alias_similarity = self._list_similarity(self.aliases, other.aliases)
        score += alias_similarity * 0.1
        total_weight += 0.1
        
        return score / total_weight if total_weight > 0 else 0.0
    
    def _string_similarity(self, str1: str, str2: str) -> float:
        """Calculate string similarity using simple algorithm."""
        if not str1 or not str2:
            return 0.0
        
        str1, str2 = str1.lower().strip(), str2.lower().strip()
        
        if str1 == str2:
            return 1.0
        
        # Simple Jaccard similarity on words
        words1 = set(str1.split())
        words2 = set(str2.split())
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def _list_similarity(self, list1: List[str], list2: List[str]) -> float:
        """Calculate similarity between two lists."""
        if not list1 or not list2:
            return 0.0
        
        set1 = set(item.lower().strip() for item in list1)
        set2 = set(item.lower().strip() for item in list2)
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        return intersection / union if union > 0 else 0.0
    
    # ======================== SERIALIZATION METHODS ========================
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert entity to dictionary."""
        return {
            'entity_id': str(self.entity_id),
            'name': self.name,
            'entity_type': self.entity_type.value,
            'programs': self.programs,
            'aliases': self.aliases,
            'addresses': self.addresses,
            'dates_of_birth': self.dates_of_birth,
            'places_of_birth': self.places_of_birth,
            'nationalities': self.nationalities,
            'remarks': self.remarks,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'content_hash': str(self.content_hash) if self.content_hash else None,
            'risk_score': self.calculate_risk_score(),
            'risk_level': self.get_risk_level().value
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SanctionedEntity':
        """Create entity from dictionary."""
        # Parse entity_id
        entity_id_str = data.get('entity_id', '')
        if ':' in entity_id_str:
            source_str, uid = entity_id_str.split(':', 1)
            source = SanctionsSource(source_str)
        else:
            # Fallback parsing
            source = SanctionsSource(data.get('source', 'US_OFAC'))
            uid = data.get('uid', '')
        
        entity_id = EntityId(source=source, uid=uid)
        
        # Parse dates
        def parse_date(date_str: Optional[str]) -> Optional[datetime]:
            if not date_str:
                return None
            try:
                return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            except:
                return None
        
        return cls(
            entity_id=entity_id,
            name=data['name'],
            entity_type=EntityType(data['entity_type']),
            programs=data.get('programs', []),
            aliases=data.get('aliases', []),
            addresses=data.get('addresses', []),
            dates_of_birth=data.get('dates_of_birth', []),
            places_of_birth=data.get('places_of_birth', []),
            nationalities=data.get('nationalities', []),
            remarks=data.get('remarks'),
            is_active=data.get('is_active', True),
            created_at=parse_date(data.get('created_at')),
            updated_at=parse_date(data.get('updated_at')),
            last_seen=parse_date(data.get('last_seen'))
        )
    
    def __str__(self) -> str:
        return f"SanctionedEntity({self.entity_id}, {self.name}, {self.entity_type.value})"
    
    def __repr__(self) -> str:
        return (
            f"SanctionedEntity("
            f"entity_id={self.entity_id}, "
            f"name='{self.name}', "
            f"entity_type={self.entity_type.value}, "
            f"programs={len(self.programs)}, "
            f"risk_level={self.get_risk_level().value})"
        )


# ======================== DOMAIN SERVICES ========================

class EntityComparisonService:
    """Service for comparing entities and detecting duplicates."""
    
    def __init__(self):
        self.logger = get_logger("domain.entity_comparison")
    
    def find_potential_duplicates(
        self, 
        entities: List[SanctionedEntity], 
        similarity_threshold: float = 0.8
    ) -> List[List[SanctionedEntity]]:
        """Find groups of potential duplicate entities."""
        self.logger.info(f"Analyzing {len(entities)} entities for duplicates")
        
        duplicate_groups = []
        processed = set()
        
        for i, entity1 in enumerate(entities):
            if i in processed:
                continue
            
            group = [entity1]
            processed.add(i)
            
            for j, entity2 in enumerate(entities[i+1:], i+1):
                if j in processed:
                    continue
                
                similarity = entity1.similarity_score(entity2)
                if similarity >= similarity_threshold:
                    group.append(entity2)
                    processed.add(j)
            
            if len(group) > 1:
                duplicate_groups.append(group)
        
        self.logger.info(f"Found {len(duplicate_groups)} potential duplicate groups")
        return duplicate_groups
    
    def compare_entities(
        self, 
        entity1: SanctionedEntity, 
        entity2: SanctionedEntity
    ) -> Dict[str, Any]:
        """Detailed comparison between two entities."""
        similarity = entity1.similarity_score(entity2)
        field_changes = entity1.get_field_changes(entity2)
        
        return {
            'entity1': entity1.to_dict(),
            'entity2': entity2.to_dict(),
            'similarity_score': similarity,
            'field_differences': field_changes,
            'potential_duplicate': similarity >= 0.7,
            'same_source': entity1.entity_id.source == entity2.entity_id.source,
            'same_type': entity1.entity_type == entity2.entity_type
        }