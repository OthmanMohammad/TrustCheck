"""
API Schemas (DTOs) Package

Centralized location for all API request/response models with:
- Pydantic validation
- Type safety
- Automatic OpenAPI documentation
- Clean separation from domain models
"""

# Base schemas
from src.api.schemas.base import (
    # Base classes
    BaseSchema,
    TimestampedSchema,
    
    # Request models
    PaginationRequest,
    FilterRequest,
    DateRangeFilter,
    
    # Response models
    BaseResponse,
    PaginatedResponse,
    ResponseMetadata,
    PaginationMetadata,
    ErrorDetail,
    ErrorResponse,
    
    # Validation utilities
    StrictString,
    EntityUID,
)

# Entity schemas
from src.api.schemas.entity import (
    # Value objects
    AddressDTO,
    PersonalInfoDTO,
    
    # Request models
    EntitySearchRequest,
    EntityFilterRequest,
    EntityBulkRequest,
    EntityCreateRequest,
    EntityUpdateRequest,
    
    # Response models
    EntitySummaryDTO,
    EntityDetailDTO,
    EntityStatistics,
    EntityResponse,
    EntityListResponse,
    EntitySearchResponse,
    EntityBulkResponse,
    
    # Conversion functions
    entity_domain_to_dto,
    entity_domain_to_summary,
)

# Change detection schemas
from src.api.schemas.change_detection import (
    # Field change models
    FieldChangeDTO,
    
    # Change event models
    ChangeEventSummaryDTO,
    ChangeEventDetailDTO,
    ChangeFilterRequest,
    ChangeSummaryRequest,
    CriticalChangesRequest,
    
    # Scraper run models
    ScraperRunSummaryDTO,
    ScraperRunDetailDTO,
    ScraperRunRequest,
    
    # Response models
    ChangeSummaryDTO,
    ScrapingStatusDTO,
    NotificationStatusDTO,
    ChangeEventResponse,
    ChangeEventListResponse,
    CriticalChangesResponse,
    ChangeSummaryResponse,
    ScraperRunResponse,
    ScraperRunListResponse,
    ScrapingStatusResponse,
    
    # Conversion functions
    change_event_domain_to_summary,
    change_event_domain_to_detail,
    scraper_run_domain_to_summary,
    scraper_run_domain_to_detail,
)

# ======================== SCHEMA REGISTRY ========================

class SchemaRegistry:
    """
    Registry of all API schemas for documentation and validation.
    """
    
    # Request schemas
    REQUEST_SCHEMAS = {
        'EntitySearchRequest': EntitySearchRequest,
        'EntityFilterRequest': EntityFilterRequest,
        'EntityBulkRequest': EntityBulkRequest,
        'EntityCreateRequest': EntityCreateRequest,
        'EntityUpdateRequest': EntityUpdateRequest,
        'ChangeFilterRequest': ChangeFilterRequest,
        'ChangeSummaryRequest': ChangeSummaryRequest,
        'CriticalChangesRequest': CriticalChangesRequest,
        'ScraperRunRequest': ScraperRunRequest,
        'PaginationRequest': PaginationRequest,
        'FilterRequest': FilterRequest,
        'DateRangeFilter': DateRangeFilter,
    }
    
    # Response schemas
    RESPONSE_SCHEMAS = {
        'EntityResponse': EntityResponse,
        'EntityListResponse': EntityListResponse,
        'EntitySearchResponse': EntitySearchResponse,
        'EntityBulkResponse': EntityBulkResponse,
        'ChangeEventResponse': ChangeEventResponse,
        'ChangeEventListResponse': ChangeEventListResponse,
        'CriticalChangesResponse': CriticalChangesResponse,
        'ChangeSummaryResponse': ChangeSummaryResponse,
        'ScraperRunResponse': ScraperRunResponse,
        'ScraperRunListResponse': ScraperRunListResponse,
        'ScrapingStatusResponse': ScrapingStatusResponse,
        'ErrorResponse': ErrorResponse,
        'BaseResponse': BaseResponse,
        'PaginatedResponse': PaginatedResponse,
    }
    
    # DTO schemas (data models)
    DTO_SCHEMAS = {
        'EntitySummaryDTO': EntitySummaryDTO,
        'EntityDetailDTO': EntityDetailDTO,
        'AddressDTO': AddressDTO,
        'PersonalInfoDTO': PersonalInfoDTO,
        'ChangeEventSummaryDTO': ChangeEventSummaryDTO,
        'ChangeEventDetailDTO': ChangeEventDetailDTO,
        'FieldChangeDTO': FieldChangeDTO,
        'ScraperRunSummaryDTO': ScraperRunSummaryDTO,
        'ScraperRunDetailDTO': ScraperRunDetailDTO,
        'ChangeSummaryDTO': ChangeSummaryDTO,
        'ScrapingStatusDTO': ScrapingStatusDTO,
        'NotificationStatusDTO': NotificationStatusDTO,
        'EntityStatistics': EntityStatistics,
    }
    
    @classmethod
    def get_all_schemas(cls):
        """Get all registered schemas."""
        return {
            **cls.REQUEST_SCHEMAS,
            **cls.RESPONSE_SCHEMAS,
            **cls.DTO_SCHEMAS,
        }
    
    @classmethod
    def get_request_schema(cls, name: str):
        """Get a request schema by name."""
        return cls.REQUEST_SCHEMAS.get(name)
    
    @classmethod
    def get_response_schema(cls, name: str):
        """Get a response schema by name."""
        return cls.RESPONSE_SCHEMAS.get(name)
    
    @classmethod
    def get_dto_schema(cls, name: str):
        """Get a DTO schema by name."""
        return cls.DTO_SCHEMAS.get(name)
    
    @classmethod
    def validate_schema_name(cls, name: str) -> bool:
        """Check if a schema name is registered."""
        return name in cls.get_all_schemas()

# ======================== OPENAPI CUSTOMIZATION ========================

def customize_openapi_schema(openapi_schema: dict) -> dict:
    """
    Customize OpenAPI schema generation for better documentation.
    
    This function can be used to enhance the auto-generated OpenAPI
    documentation with additional examples, descriptions, etc.
    """
    # Add global tags
    if 'tags' not in openapi_schema:
        openapi_schema['tags'] = []
    
    openapi_schema['tags'].extend([
        {
            'name': 'Entities',
            'description': 'Sanctioned entity operations'
        },
        {
            'name': 'Changes',
            'description': 'Change detection and monitoring'
        },
        {
            'name': 'Scraping',
            'description': 'Data source scraping operations'
        },
        {
            'name': 'System',
            'description': 'System health and statistics'
        }
    ])
    
    # Add security schemes
    if 'components' not in openapi_schema:
        openapi_schema['components'] = {}
    
    if 'securitySchemes' not in openapi_schema['components']:
        openapi_schema['components']['securitySchemes'] = {}
    
    openapi_schema['components']['securitySchemes'].update({
        'ApiKeyAuth': {
            'type': 'apiKey',
            'in': 'header',
            'name': 'X-API-Key'
        },
        'BearerAuth': {
            'type': 'http',
            'scheme': 'bearer',
            'bearerFormat': 'JWT'
        }
    })
    
    return openapi_schema

# ======================== EXAMPLE DATA GENERATORS ========================

def generate_example_data():
    """
    Generate example data for API documentation.
    
    Returns example instances of all major DTOs for use in
    API documentation and testing.
    """
    from datetime import datetime
    from uuid import uuid4
    
    examples = {
        'entity_summary': EntitySummaryDTO(
            uid="OFAC-12345",
            name="John Doe",
            entity_type="PERSON",
            source="OFAC",
            programs=["SDGT", "CYBER"],
            is_active=True,
            is_high_risk=True,
            last_updated=datetime.utcnow(),
            alias_count=3,
            address_count=2
        ),
        
        'change_event': ChangeEventSummaryDTO(
            event_id=uuid4(),
            entity_uid="OFAC-12345",
            entity_name="John Doe",
            source="OFAC",
            change_type="MODIFIED",
            risk_level="HIGH",
            change_summary="Programs updated: added CYBER",
            detected_at=datetime.utcnow(),
            notification_sent=False
        ),
        
        'scraper_run': ScraperRunSummaryDTO(
            run_id="OFAC_1234567890",
            source="OFAC",
            status="SUCCESS",
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            duration_seconds=45.2,
            entities_processed=8500,
            total_changes=12,
            error_message=None
        ),
        
        'error_response': ErrorResponse(
            success=False,
            error=ErrorDetail(
                code="ENTITY_NOT_FOUND",
                message="Entity with UID 'INVALID-123' not found",
                field="uid",
                context={"uid": "INVALID-123"}
            ),
            suggestions=["Check the entity UID is correct", "Use the search endpoint to find entities"],
            metadata=ResponseMetadata(
                timestamp=datetime.utcnow(),
                request_id="req-123456"
            )
        )
    }
    
    return examples

# ======================== EXPORTS ========================

__all__ = [
    # Base schemas
    'BaseSchema',
    'TimestampedSchema',
    'PaginationRequest',
    'FilterRequest',
    'DateRangeFilter',
    'BaseResponse',
    'PaginatedResponse',
    'ResponseMetadata',
    'PaginationMetadata',
    'ErrorDetail',
    'ErrorResponse',
    'StrictString',
    'EntityUID',
    
    # Entity schemas
    'AddressDTO',
    'PersonalInfoDTO',
    'EntitySearchRequest',
    'EntityFilterRequest',
    'EntityBulkRequest',
    'EntityCreateRequest',
    'EntityUpdateRequest',
    'EntitySummaryDTO',
    'EntityDetailDTO',
    'EntityStatistics',
    'EntityResponse',
    'EntityListResponse',
    'EntitySearchResponse',
    'EntityBulkResponse',
    'entity_domain_to_dto',
    'entity_domain_to_summary',
    
    # Change detection schemas
    'FieldChangeDTO',
    'ChangeEventSummaryDTO',
    'ChangeEventDetailDTO',
    'ChangeFilterRequest',
    'ChangeSummaryRequest',
    'CriticalChangesRequest',
    'ScraperRunSummaryDTO',
    'ScraperRunDetailDTO',
    'ScraperRunRequest',
    'ChangeSummaryDTO',
    'ScrapingStatusDTO',
    'NotificationStatusDTO',
    'ChangeEventResponse',
    'ChangeEventListResponse',
    'CriticalChangesResponse',
    'ChangeSummaryResponse',
    'ScraperRunResponse',
    'ScraperRunListResponse',
    'ScrapingStatusResponse',
    'change_event_domain_to_summary',
    'change_event_domain_to_detail',
    'scraper_run_domain_to_summary',
    'scraper_run_domain_to_detail',
    
    # Registry and utilities
    'SchemaRegistry',
    'customize_openapi_schema',
    'generate_example_data',
]