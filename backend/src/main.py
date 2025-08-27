"""
TrustCheck FastAPI Application
"""

from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any
import uuid

# Core imports with new structure
from src.core.config import settings
from src.core.exceptions import (
    TrustCheckError, ValidationError, handle_exception, 
    create_error_response, ConfigurationError
)
from src.core.enums import Environment, APIStatus, ScrapingStatus
from src.core.logging_config import (
    get_logger, LoggingContext, log_exception, log_performance,
    REQUEST_ID_VAR, USER_ID_VAR
)

# Database imports
from src.infrastructure.database.connection import get_db, create_tables, check_db_health, get_db_stats  
from src.infrastructure.database.models import SanctionedEntity, ScrapingLog, ChangeEvent, ScraperRun

# Business logic imports  
from src.scrapers import scraper_registry
from src.scrapers.registry import Region, ScraperTier

# API imports
from src.api.change_detection import router as change_detection_router

# Initialize logger
logger = get_logger(__name__)

# ======================== MIDDLEWARE ========================

async def add_request_correlation_id(request: Request, call_next):
    """Add correlation ID to all requests."""
    
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
                "user_agent": request.headers.get("user-agent")
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
    """Handle FastAPI validation errors."""
    
    validation_error = ValidationError(
        message="Request validation failed",
        context={"errors": exc.errors()},
        user_message="Invalid request data provided"
    )
    
    log_exception(logger, validation_error, {
        "request_path": str(request.url.path),
        "request_method": request.method,
        "validation_errors": exc.errors()
    })
    
    return JSONResponse(
        status_code=422,
        content=create_error_response(validation_error)
    )

async def trustcheck_exception_handler(request: Request, exc: TrustCheckError):
    """Handle custom TrustCheck exceptions."""
    
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
    
    return JSONResponse(
        status_code=status_code,
        content=create_error_response(exc)
    )

async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    
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
    
    return JSONResponse(
        status_code=500,
        content=create_error_response(trustcheck_error)
    )

# ======================== APPLICATION LIFESPAN ========================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown with proper logging."""
    
    startup_start = time.time()
    
    try:
        logger.info("🚀 TrustCheck API starting up...", extra={
            "version": settings.version,
            "environment": settings.environment.value,
            "debug": settings.debug
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
            "✅ TrustCheck API startup completed",
            extra={
                "startup_time_ms": startup_time,
                "database_healthy": True,
                "change_detection_enabled": True
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
        logger.info("🛑 TrustCheck API shutting down...")
        logger.info("✅ Shutdown completed")

# ======================== CREATE APPLICATION ========================

app = FastAPI(
    title=f"{settings.project_name} API",
    description=settings.description,
    version=settings.version,
    lifespan=lifespan,
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)

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
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# ======================== EXCEPTION HANDLERS ========================

app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(TrustCheckError, trustcheck_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

# ======================== INCLUDE ROUTERS ========================

app.include_router(change_detection_router)

# ======================== HEALTH ENDPOINTS ========================

@app.get("/health")
async def health_check(request: Request, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Comprehensive health check with proper logging."""
    
    health_start = time.time()
    
    try:
        # Check database
        db_healthy = check_db_health()
        
        # Check change detection tables  
        change_detection_healthy = True
        try:
            db.query(ChangeEvent).count()
            db.query(ScraperRun).count()
        except Exception as e:
            logger.error(f"Change detection health check failed: {e}")
            change_detection_healthy = False
        
        # Overall health status
        overall_healthy = db_healthy and change_detection_healthy
        
        health_status = {
            "status": "healthy" if overall_healthy else "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": settings.version,
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
                "change_detection": "healthy" if change_detection_healthy else "unhealthy",
            },
            "features": [
                "Real-time change detection",
                "Risk-based notifications",
                "Comprehensive audit trail", 
                "Multiple sanctions sources",
                "Structured logging",
                "Exception handling"
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
            change_detection_healthy=change_detection_healthy
        )
        
        return health_status
        
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        raise

@app.get("/metrics")
async def get_metrics(request: Request, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """System metrics for monitoring (development only)."""
    
    if settings.is_production:
        raise HTTPException(status_code=404, detail="Not found")
    
    try:
        db_stats = get_db_stats()
        entity_count = db.query(SanctionedEntity).count()
        
        # Change detection metrics
        total_changes = db.query(ChangeEvent).count()
        recent_changes = db.query(ChangeEvent).filter(
            ChangeEvent.detected_at >= datetime.utcnow() - timedelta(hours=24)
        ).count()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": getattr(request.state, 'request_id', None),
            "database": db_stats,
            "entities": {
                "total_count": entity_count,
                "by_source": {
                    source: db.query(SanctionedEntity).filter(
                        SanctionedEntity.source == source
                    ).count()
                    for source in ["OFAC", "UN", "EU", "UK_HMT"]
                }
            },
            "change_detection": {
                "total_changes": total_changes,
                "recent_changes_24h": recent_changes,
                "system_status": "operational"
            }
        }
        
    except Exception as e:
        handle_exception(e, logger, context={"endpoint": "metrics"})
        raise

# ======================== ROOT ENDPOINT ========================

@app.get("/")
async def read_root(request: Request) -> Dict[str, Any]:
    """Root endpoint with API information."""
    
    return {
        "service": settings.project_name,
        "version": settings.version,
        "description": settings.description,
        "status": APIStatus.SUCCESS.value,
        "environment": settings.environment.value,
        "timestamp": datetime.utcnow().isoformat(),
        "request_id": getattr(request.state, 'request_id', None),
        "endpoints": {
            "health": "/health",
            "metrics": "/metrics" if settings.debug else "disabled",
            "documentation": "/docs" if settings.docs_enabled else "disabled",
            
            # Change detection endpoints
            "changes": f"{settings.api_v1_prefix}/change-detection/changes",
            "changes_summary": f"{settings.api_v1_prefix}/change-detection/changes/summary", 
            "scraper_runs": f"{settings.api_v1_prefix}/change-detection/runs",
            "system_status": f"{settings.api_v1_prefix}/change-detection/status"
        },
        "features": [
            "Production-grade logging",
            "Structured exception handling", 
            "Request correlation", 
            "Real-time change detection",
            "Risk-based notifications",
            "Multiple sanctions sources",
            "PostgreSQL database",
            "Redis caching",
            "RESTful API"
        ]
    }

# ======================== EXISTING ENDPOINTS (Updated) ========================

@app.get("/scrapers")
async def list_scrapers(request: Request):
    """List available scrapers with enhanced logging."""
    
    try:
        all_scrapers = scraper_registry.get_all_scrapers()
        available_scrapers = scraper_registry.list_available_scrapers()
        
        scrapers_data = {}
        for name, metadata in all_scrapers.items():
            scrapers_data[name] = {
                "name": metadata.name,
                "region": metadata.region.value,
                "tier": metadata.tier.value,
                "update_frequency": metadata.update_frequency,
                "entity_count": metadata.entity_count,
                "complexity": metadata.complexity,
                "data_format": metadata.data_format,
                "requires_auth": metadata.requires_auth,
                "change_detection_enabled": True
            }
        
        logger.info(f"Listed {len(available_scrapers)} available scrapers")
        
        return {
            "status": APIStatus.SUCCESS.value,
            "scrapers": scrapers_data,
            "available_scrapers": available_scrapers,
            "total_count": len(available_scrapers),
            "change_detection_enabled": True,
            "request_id": getattr(request.state, 'request_id', None),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        handle_exception(e, logger, context={"endpoint": "list_scrapers"})
        raise

# Add remaining endpoints with similar patterns...
# (They would follow the same structure with proper logging and exception handling)

if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"Starting TrustCheck API server on port 8000")
    logger.info(f"Environment: {settings.environment.value}")
    logger.info(f"Debug mode: {settings.debug}")
    
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.observability.log_level.value.lower(),
        log_config=None  # We handle logging ourselves
    )