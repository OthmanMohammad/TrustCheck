"""
Entity schemas for sanctioned entities API.

DTOs for entity-related requests and responses.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum

from src.api.schemas.base import (
    BaseSchema, TimestampedSchema, PaginationRequest, FilterRequest,
    BaseResponse, PaginatedResponse, StrictString, EntityUID,
    ENTITY_NAME_FIELD, SOURCE_FIELD
)

# Import enums from core
from src.core.enums import EntityType, DataSource

# ======================== ENTITY VALUE OBJECTS ========================

class AddressDTO(BaseSchema):
    """Address data transfer object."""
    street: Optional[str] = Field(None, max_length=500)
    city: Optional[str] = Field(None, max_length=200)
    state_province: Optional[str] = Field(None, max_length=200)
    postal_code: Optional[str] = Field(None, max_length=50)
    country: Optional[str] = Field(None, max_length=100)
    
    @model_validator(mode='after')
    def validate_address(self) -> 'AddressDTO':
        """Ensure address has at least some information."""
        if not any([self.street, self.city, self.country]):
            raise ValueError("Address must have at least one field")
        return self
    
    def to_string(self) -> str:
        """Convert to string representation."""
        parts = [self.street, self.city, self.state_province, self.postal_code, self.country]
        return ', '.join(part for part in parts if part)

class PersonalInfoDTO(BaseSchema):
    """Personal information for individuals."""
    first_name: Optional[str] = Field(None, max_length=200)
    last_name: Optional[str] = Field(None, max_length=200)
    date_of_birth: Optional[str] = Field(None, pattern=r'^\d{4}-\d{2}-\d{2}$|^\d{4}$')
    place_of_birth: Optional[str] = Field(None, max_length=500)
    nationality: Optional[str] = Field(None, max_length=100)

# ======================== ENTITY REQUESTS ========================

class EntitySearchRequest(PaginationRequest):
    """Request for entity search."""
    query: str = Field(
        ...,
        min_length=2,
        max_length=200,
        description="Search query (name or alias)"
    )
    fuzzy: bool = Field(
        default=False,
        description="Enable fuzzy matching"
    )
    sources: Optional[List[DataSource]] = Field(
        None,
        description="Filter by data sources"
    )
    entity_types: Optional[List[EntityType]] = Field(
        None,
        description="Filter by entity types"
    )

class EntityFilterRequest(PaginationRequest, FilterRequest):
    """Request for entity listing with filters."""
    source: Optional[DataSource] = Field(None, description="Filter by data source")
    entity_type: Optional[EntityType] = Field(None, description="Filter by entity type")
    program: Optional[str] = Field(None, max_length=100, description="Filter by sanctions program")
    nationality: Optional[str] = Field(None, max_length=100, description="Filter by nationality")
    high_risk_only: bool = Field(default=False, description="Return only high-risk entities")

class EntityBulkRequest(BaseSchema):
    """Request for bulk entity operations."""
    entity_uids: List[EntityUID] = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="List of entity UIDs"
    )
    operation: str = Field(
        ...,
        pattern="^(activate|deactivate|delete)$",
        description="Operation to perform"
    )

# ======================== ENTITY RESPONSES ========================

class EntitySummaryDTO(BaseSchema):
    """Summary view of an entity (for lists)."""
    uid: EntityUID = Field(..., description="Unique identifier")
    name: str = ENTITY_NAME_FIELD
    entity_type: EntityType = Field(..., description="Entity type")
    source: DataSource = SOURCE_FIELD
    programs: List[str] = Field(default_factory=list, description="Sanctions programs")
    is_active: bool = Field(..., description="Whether entity is active")
    is_high_risk: bool = Field(..., description="High risk indicator")
    last_updated: Optional[datetime] = Field(None, description="Last update timestamp")
    
    # Summary fields
    alias_count: int = Field(default=0, description="Number of aliases")
    address_count: int = Field(default=0, description="Number of addresses")

class EntityDetailDTO(TimestampedSchema):
    """Detailed view of an entity."""
    uid: EntityUID = Field(..., description="Unique identifier")
    name: str = ENTITY_NAME_FIELD
    entity_type: EntityType = Field(..., description="Entity type")
    source: DataSource = SOURCE_FIELD
    
    # Core sanctions data
    programs: List[str] = Field(default_factory=list, description="Sanctions programs")
    aliases: List[str] = Field(default_factory=list, description="Alternative names")
    addresses: List[AddressDTO] = Field(default_factory=list, description="Known addresses")
    
    # Personal information (for individuals)
    personal_info: Optional[PersonalInfoDTO] = Field(None, description="Personal information")
    
    # Additional data
    nationalities: List[str] = Field(default_factory=list, description="Nationalities")
    remarks: Optional[str] = Field(None, description="Additional remarks")
    
    # Metadata
    is_active: bool = Field(..., description="Whether entity is active")
    is_high_risk: bool = Field(..., description="High risk indicator")
    content_hash: Optional[str] = Field(None, description="Content hash for change detection")
    last_seen: Optional[datetime] = Field(None, description="Last seen in source data")
    
    @field_validator('programs', 'aliases', 'nationalities')
    @classmethod
    def remove_duplicates(cls, v: List[str]) -> List[str]:
        """Remove duplicates while preserving order."""
        seen = set()
        return [x for x in v if not (x in seen or seen.add(x))]

class EntityCreateRequest(BaseSchema):
    """Request to create a new entity."""
    uid: EntityUID = Field(..., description="Unique identifier")
    name: str = ENTITY_NAME_FIELD
    entity_type: EntityType = Field(..., description="Entity type")
    source: DataSource = SOURCE_FIELD
    programs: List[str] = Field(default_factory=list, description="Sanctions programs")
    aliases: Optional[List[str]] = Field(None, description="Alternative names")
    addresses: Optional[List[AddressDTO]] = Field(None, description="Known addresses")
    personal_info: Optional[PersonalInfoDTO] = Field(None, description="Personal information")
    nationalities: Optional[List[str]] = Field(None, description="Nationalities")
    remarks: Optional[str] = Field(None, max_length=5000, description="Additional remarks")
    
    @model_validator(mode='after')
    def validate_personal_info(self) -> 'EntityCreateRequest':
        """Ensure personal_info is only for persons."""
        if self.personal_info and self.entity_type != EntityType.PERSON:
            raise ValueError("personal_info is only valid for PERSON entities")
        return self

class EntityUpdateRequest(BaseSchema):
    """Request to update an existing entity."""
    name: Optional[str] = Field(None, min_length=1, max_length=500)
    programs: Optional[List[str]] = Field(None)
    aliases: Optional[List[str]] = Field(None)
    addresses: Optional[List[AddressDTO]] = Field(None)
    personal_info: Optional[PersonalInfoDTO] = Field(None)
    nationalities: Optional[List[str]] = Field(None)
    remarks: Optional[str] = Field(None, max_length=5000)
    is_active: Optional[bool] = Field(None)
    
    @model_validator(mode='after')
    def validate_has_updates(self) -> 'EntityUpdateRequest':
        """Ensure at least one field is being updated."""
        if not any(getattr(self, field) is not None for field in self.model_fields):
            raise ValueError("At least one field must be provided for update")
        return self

# ======================== ENTITY STATISTICS ========================

class EntityStatistics(BaseSchema):
    """Entity statistics."""
    total_active: int = Field(..., description="Total active entities")
    total_inactive: int = Field(..., description="Total inactive entities")
    by_source: Dict[str, int] = Field(..., description="Count by data source")
    by_type: Dict[str, int] = Field(..., description="Count by entity type")
    by_risk_level: Dict[str, int] = Field(default_factory=dict, description="Count by risk level")
    last_updated: datetime = Field(..., description="Statistics calculation time")

# ======================== RESPONSE WRAPPERS ========================

class EntityResponse(BaseResponse[EntityDetailDTO]):
    """Single entity response."""
    pass

class EntityListResponse(PaginatedResponse[List[EntitySummaryDTO]]):
    """Entity list response with pagination."""
    filters: Optional[EntityFilterRequest] = Field(
        None,
        description="Applied filters"
    )
    statistics: Optional[EntityStatistics] = Field(
        None,
        description="Entity statistics"
    )

class EntitySearchResponse(PaginatedResponse[List[EntitySummaryDTO]]):
    """Entity search response."""
    query: str = Field(..., description="Search query")
    fuzzy_matching: bool = Field(..., description="Whether fuzzy matching was used")
    
    class SearchResult(EntitySummaryDTO):
        """Search result with relevance score."""
        relevance_score: float = Field(
            ...,
            ge=0.0,
            le=1.0,
            description="Search relevance score"
        )

class EntityBulkResponse(BaseResponse[Dict[str, Any]]):
    """Bulk operation response."""
    operation: str = Field(..., description="Operation performed")
    processed: int = Field(..., description="Number of entities processed")
    succeeded: int = Field(..., description="Number of successful operations")
    failed: int = Field(..., description="Number of failed operations")
    errors: Optional[List[Dict[str, str]]] = Field(None, description="Error details")

# ======================== DOMAIN CONVERSION ========================

def entity_domain_to_dto(entity: Any) -> EntityDetailDTO:
    """Convert domain entity to detailed DTO."""
    from src.core.domain.entities import SanctionedEntityDomain, Address
    
    # Convert addresses
    address_dtos = []
    if hasattr(entity, 'addresses') and entity.addresses:
        for addr in entity.addresses:
            if isinstance(addr, Address):
                address_dtos.append(AddressDTO(
                    street=addr.street,
                    city=addr.city,
                    state_province=addr.state_province,
                    postal_code=addr.postal_code,
                    country=addr.country
                ))
    
    # Convert personal info
    personal_info_dto = None
    if hasattr(entity, 'personal_info') and entity.personal_info:
        personal_info_dto = PersonalInfoDTO(
            first_name=entity.personal_info.first_name,
            last_name=entity.personal_info.last_name,
            date_of_birth=entity.personal_info.date_of_birth,
            place_of_birth=entity.personal_info.place_of_birth,
            nationality=entity.personal_info.nationality
        )
    
    return EntityDetailDTO(
        uid=entity.uid,
        name=entity.name,
        entity_type=entity.entity_type,
        source=entity.source,
        programs=entity.programs or [],
        aliases=entity.aliases or [],
        addresses=address_dtos,
        personal_info=personal_info_dto,
        nationalities=entity.nationalities or [],
        remarks=entity.remarks,
        is_active=entity.is_active,
        is_high_risk=entity.is_high_risk,
        content_hash=entity.content_hash,
        last_seen=entity.last_seen,
        created_at=entity.created_at,
        updated_at=entity.updated_at
    )

def entity_domain_to_summary(entity: Any) -> EntitySummaryDTO:
    """Convert domain entity to summary DTO."""
    return EntitySummaryDTO(
        uid=entity.uid,
        name=entity.name,
        entity_type=entity.entity_type,
        source=entity.source,
        programs=entity.programs or [],
        is_active=entity.is_active,
        is_high_risk=entity.is_high_risk,
        last_updated=entity.updated_at,
        alias_count=len(entity.aliases) if entity.aliases else 0,
        address_count=len(entity.addresses) if entity.addresses else 0
    )

# ======================== EXPORTS ========================

__all__ = [
    # Value objects
    'AddressDTO',
    'PersonalInfoDTO',
    
    # Request models
    'EntitySearchRequest',
    'EntityFilterRequest',
    'EntityBulkRequest',
    'EntityCreateRequest',
    'EntityUpdateRequest',
    
    # Response models
    'EntitySummaryDTO',
    'EntityDetailDTO',
    'EntityStatistics',
    'EntityResponse',
    'EntityListResponse',
    'EntitySearchResponse',
    'EntityBulkResponse',
    
    # Conversion functions
    'entity_domain_to_dto',
    'entity_domain_to_summary'
]