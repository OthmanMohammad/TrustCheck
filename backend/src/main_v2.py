"""
TrustCheck FastAPI Application v2

Updated with Phase 3 improvements:
- Full request/response validation with Pydantic DTOs
- Type safety throughout the API layer
- Automatic OpenAPI documentation from schemas
- Clean separation between API and domain layers
"""

from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
import logging
import time
from datetime import datetime
from typing import Dict, Any
import uuid

# Core imports
from src.core.config import settings
from src.core.exceptions import (
    TrustCheckError, ValidationError, handle_exception,
    ConfigurationError
)
from src.core.enums import Environment, APIStatus
from src.core.logging_config import (
    get_logger, LoggingContext, log_exception, log_performance,
    REQUEST_ID_VAR
)

# Database imports
from src.infrastructure.database.connection import (
    get_db, create_tables, check_db_health, get_db_stats
)

# API imports
from src.api.v2.change_detection import router as v2_router
from src.api.change_detection import router as v1_router  # Keep v1 for backward compatibility

# Schema imports for OpenAPI customization
from src.api.schemas import (
    customize_openapi_schema,
    ErrorResponse, ErrorDetail, ResponseMetadata
)

# Initialize logger
logger = get_logger(__name__)

# ======================== MIDDLEWARE ========================

async def add_request_correlation_id(request: Request, call_next):
    """Add correlation ID to all requests with enhanced logging."""
    
    # Get or generate request ID
    request_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())
    
    # Set context variables for logging
    with LoggingContext(request_id=request_id):
        # Add to request state
        request.state.request_id = request_id
        
        # Log request start
        start_time = time.time()
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={
                "request_method": request.method,
                "request_path": str(request.url.path),
                "request_query": str(request.url.query),
                "client_host": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
                "api_version": "v2" if "/v2/" in str(request.url.path) else "v1"
            }
        )
        
        # Process request
        response = await call_next(request)
        
        # Log request completion
        duration_ms = (time.time() - start_time) * 1000
        log_performance(
            logger,
            f"{request.method} {request.url.path}",
            duration_ms,
            success=response.status_code < 400,
            status_code=response.status_code,
            request_method=request.method,
            request_path=str(request.url.path)
        )
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        
        return response

# ======================== EXCEPTION HANDLERS ========================

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle FastAPI/Pydantic validation errors with proper DTO response."""
    
    # Extract validation errors
    errors = exc.errors()
    
    # Create structured error response using DTOs
    error_response = ErrorResponse(
        success=False,
        error=ErrorDetail(
            code="VALIDATION_ERROR",
            message="Request validation failed",
            context={"validation_errors": errors}
        ),
        suggestions=[
            "Check the request format against the API documentation",
            "Ensure all required fields are provided",
            "Verify field types match the schema"
        ],
        metadata=ResponseMetadata(
            timestamp=datetime.utcnow(),
            request_id=getattr(request.state, 'request_id', None)
        )
    )
    
    log_exception(logger, ValidationError("Request validation failed"), {
        "request_path": str(request.url.path),
        "request_method": request.method,
        "validation_errors": errors
    })
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response.model_dump()
    )

async def trustcheck_exception_handler(request: Request, exc: TrustCheckError):
    """Handle custom TrustCheck exceptions with DTO response."""
    
    log_exception(logger, exc, {
        "request_path": str(request.url.path),
        "request_method": request.method,
        "error_code": exc.error_code,
        "error_category": exc.category.value
    })
    
    # Map categories to HTTP status codes
    status_code_map = {
        "validation": 400,
        "authentication": 401,
        "authorization": 403,
        "not_found": 404,
        "conflict": 409,
        "rate_limit": 429,
        "external_service": 502,
        "database": 503,
        "business_logic": 400,
        "system": 500
    }
    
    status_code = status_code_map.get(exc.category.value, 500)
    
    # Create structured error response
    error_response = ErrorResponse(
        success=False,
        error=ErrorDetail(
            code=exc.error_code,
            message=exc.user_message,
            context=exc.context
        ),
        suggestions=exc.suggestions,
        metadata=ResponseMetadata(
            timestamp=exc.timestamp,
            request_id=getattr(request.state, 'request_id', None)
        )
    )
    
    return JSONResponse(
        status_code=status_code,
        content=error_response.model_dump()
    )

async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions with DTO response."""
    
    # Convert to TrustCheckError for consistent handling
    trustcheck_error = handle_exception(
        exc,
        logger,
        context={
            "request_path": str(request.url.path),
            "request_method": request.method,
            "request_id": getattr(request.state, 'request_id', None)
        }
    )
    
    # Create structured error response
    error_response = ErrorResponse(
        success=False,
        error=ErrorDetail(
            code="INTERNAL_ERROR",
            message="An unexpected error occurred",
            context={"request_id": getattr(request.state, 'request_id', None)}
        ),
        suggestions=["Please try again later", "Contact support if the issue persists"],
        metadata=ResponseMetadata(
            timestamp=datetime.utcnow(),
            request_id=getattr(request.state, 'request_id', None)
        )
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.model_dump()
    )

# ======================== APPLICATION LIFESPAN ========================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown with validation."""
    
    startup_start = time.time()
    
    try:
        logger.info("🚀 TrustCheck API v2 starting up...", extra={
            "version": settings.version,
            "environment": settings.environment.value,
            "debug": settings.debug,
            "features": {
                "dto_validation": True,
                "type_safety": True,
                "openapi_schemas": True
            }
        })
        
        # Validate configuration
        if not settings.database.database_url:
            raise ConfigurationError("Database URL not configured")
        
        # Initialize database
        logger.info("Initializing database...")
        create_tables()
        
        # Check database health
        if not check_db_health():
            raise ConfigurationError("Database health check failed")
        
        # Log startup completion
        startup_time = (time.time() - startup_start) * 1000
        logger.info(
            "✅ TrustCheck API v2 startup completed",
            extra={
                "startup_time_ms": startup_time,
                "database_healthy": True,
                "change_detection_enabled": True,
                "dto_validation_enabled": True,
                "api_versions": ["v1", "v2"]
            }
        )
        
        yield  # Application runs here
        
    except Exception as e:
        logger.critical(
            f"❌ Application startup failed: {e}",
            extra={"startup_error": str(e)},
            exc_info=True
        )
        raise
    
    finally:
        # Shutdown
        logger.info("🛑 TrustCheck API v2 shutting down...")
        logger.info("✅ Shutdown completed")

# ======================== CREATE APPLICATION ========================

def custom_openapi():
    """Generate custom OpenAPI schema with DTO information."""
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=f"{settings.project_name} API",
        version=settings.version,
        description=f"{settings.description}\n\n**Phase 3 Features:**\n- Full request/response validation\n- Type-safe DTOs\n- Automatic schema documentation\n- Clean API/Domain separation",
        routes=app.routes,
    )
    
    # Customize the schema
    openapi_schema = customize_openapi_schema(openapi_schema)
    
    # Add server information
    openapi_schema["servers"] = [
        {"url": "/api/v2", "description": "API v2 with DTOs (Recommended)"},
        {"url": "/api/v1", "description": "API v1 (Legacy)"}
    ]
    
    # Add external documentation
    openapi_schema["externalDocs"] = {
        "description": "TrustCheck API Documentation",
        "url": "https://trustcheck.com/docs"
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app = FastAPI(
    title=f"{settings.project_name} API",
    description=f"{settings.description}\n\n**Now with Phase 3 improvements!**",
    version=f"{settings.version}-v2",
    lifespan=lifespan,
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)

# Set custom OpenAPI schema
app.openapi = custom_openapi

# ======================== ADD MIDDLEWARE ========================

# Request correlation
app.middleware("http")(add_request_correlation_id)

# Security middleware for production
if settings.is_production:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["trustcheck.com", "*.trustcheck.com", "localhost"]
    )

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.security.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Total-Count", "X-Page-Count"]
)

# ======================== EXCEPTION HANDLERS ========================

app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(TrustCheckError, trustcheck_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

# ======================== INCLUDE ROUTERS ========================

# Include v2 router (with DTOs) as primary
app.include_router(v2_router, prefix="", tags=["API v2"])

# Include v1 router for backward compatibility
app.include_router(v1_router, prefix="/v1", tags=["API v1 (Legacy)"])

# ======================== ROOT AND HEALTH ENDPOINTS ========================

@app.get("/", tags=["System"])
async def read_root(request: Request) -> Dict[str, Any]:
    """Root endpoint with API version information."""
    
    return {
        "service": settings.project_name,
        "version": f"{settings.version}-v2",
        "description": settings.description,
        "status": APIStatus.SUCCESS.value,
        "environment": settings.environment.value,
        "timestamp": datetime.utcnow().isoformat(),
        "request_id": getattr(request.state, 'request_id', None),
        "api_versions": {
            "v2": {
                "path": "/api/v2",
                "status": "recommended",
                "features": [
                    "Full request/response validation",
                    "Type-safe DTOs",
                    "Automatic OpenAPI documentation",
                    "Clean API/Domain separation"
                ]
            },
            "v1": {
                "path": "/api/v1",
                "status": "legacy",
                "features": ["Basic functionality", "Manual validation"]
            }
        },
        "documentation": {
            "openapi": "/openapi.json",
            "swagger": "/docs",
            "redoc": "/redoc"
        },
        "phase_3_improvements": [
            "Pydantic request/response schemas",
            "Comprehensive input validation",
            "Type safety throughout API layer",
            "Structured error responses",
            "Enhanced OpenAPI documentation",
            "Domain model conversion utilities"
        ]
    }

@app.get("/health", tags=["System"])
async def health_check(request: Request, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Comprehensive health check."""
    
    health_start = time.time()
    
    try:
        # Check database
        db_healthy = check_db_health()
        
        # Check API schemas
        from src.api.schemas import SchemaRegistry
        schemas_loaded = len(SchemaRegistry.get_all_schemas()) > 0
        
        # Overall health status
        overall_healthy = db_healthy and schemas_loaded
        
        health_status = {
            "status": "healthy" if overall_healthy else "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": f"{settings.version}-v2",
            "service": settings.project_name,
            "environment": settings.environment.value,
            "request_id": getattr(request.state, 'request_id', None),
            "database": {
                "status": "connected" if db_healthy else "disconnected",
                "type": "PostgreSQL"
            },
            "components": {
                "api": "healthy",
                "database": "healthy" if db_healthy else "unhealthy",
                "dto_validation": "healthy" if schemas_loaded else "unhealthy",
                "change_detection": "healthy"
            },
            "phase_3_status": {
                "dto_schemas_loaded": schemas_loaded,
                "total_schemas": len(SchemaRegistry.get_all_schemas()) if schemas_loaded else 0,
                "validation_enabled": True,
                "type_safety": True
            },
            "features": [
                "Real-time change detection",
                "Risk-based notifications",
                "Comprehensive audit trail",
                "Multiple sanctions sources",
                "Structured logging",
                "Exception handling",
                "Request/Response validation (NEW)",
                "Type-safe DTOs (NEW)",
                "OpenAPI schema generation (NEW)"
            ]
        }
        
        # Log health check
        health_time = (time.time() - health_start) * 1000
        log_performance(
            logger,
            "health_check",
            health_time,
            success=overall_healthy,
            database_healthy=db_healthy,
            schemas_loaded=schemas_loaded
        )
        
        return health_status
        
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        raise

# ======================== METRICS ENDPOINT ========================

@app.get("/metrics", tags=["System"])
async def get_metrics(request: Request, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """System metrics including DTO validation statistics."""
    
    if settings.is_production and not request.headers.get("X-Admin-Token"):
        raise HTTPException(status_code=404, detail="Not found")
    
    try:
        from src.api.schemas import SchemaRegistry
        
        db_stats = get_db_stats()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": getattr(request.state, 'request_id', None),
            "database": db_stats,
            "api": {
                "version": "v2",
                "total_request_schemas": len(SchemaRegistry.REQUEST_SCHEMAS),
                "total_response_schemas": len(SchemaRegistry.RESPONSE_SCHEMAS),
                "total_dto_schemas": len(SchemaRegistry.DTO_SCHEMAS),
                "validation_enabled": True,
                "type_safety_enforced": True
            },
            "phase_3_metrics": {
                "schemas_registered": len(SchemaRegistry.get_all_schemas()),
                "request_validation": "enabled",
                "response_validation": "enabled",
                "openapi_generation": "automatic"
            }
        }
        
    except Exception as e:
        handle_exception(e, logger, context={"endpoint": "metrics"})
        raise

# ======================== MAIN ENTRY POINT ========================

if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"Starting TrustCheck API v2 server on port 8000")
    logger.info(f"Environment: {settings.environment.value}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info("Phase 3 Features: DTO Validation ENABLED")
    
    uvicorn.run(
        "src.main_v2:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.observability.log_level.value.lower(),
        log_config=None  # We handle logging ourselves
    )