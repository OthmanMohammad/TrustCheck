"""
TrustCheck FastAPI Application

"""

from contextlib import asynccontextmanager
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session

# Core imports - NEW STRUCTURE
from src.core.config.settings import settings
from src.core.exceptions import (
    TrustCheckError, handle_exception, ErrorCode,
    EntityNotFoundError, ValidationError, DatabaseOperationError
)
from src.core.enums import EntityType, SanctionsSource, ChangeType
from src.utils.logging import get_logger, LogContext

# Database and infrastructure - NEW STRUCTURE
from src.infrastructure.database.connection import (
    db_manager, get_db, create_tables, check_db_health, get_db_stats
)
from src.infrastructure.database.repositories.entity_repository import EntityRepository
from src.infrastructure.database.models import SanctionedEntity

# Services - NEW STRUCTURE
from src.services.entity_service import EntityService

# Scrapers - UPDATED IMPORTS
from src.scrapers.registry import scraper_registry
from src.scrapers.base.change_aware_scraper import ChangeAwareScraper

# Configure logging
logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan with comprehensive startup and shutdown."""
    
    # Startup
    logger.info("🚀 TrustCheck API starting up...")
    logger.info(f"📊 Environment: {'Development' if settings.DEBUG else 'Production'}")
    logger.info(f"🗃️ Database: {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
    
    try:
        # Initialize database
        create_tables()
        
        # Check database health
        if not check_db_health():
            raise Exception("Database health check failed")
        
        logger.info("✅ Database connection verified")
        logger.info("✅ Change detection tables ready")
        logger.info("✅ TrustCheck API startup completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        raise
    
    yield  # Application runs here
    
    # Shutdown
    logger.info("🛑 TrustCheck API shutting down...")
    logger.info("✅ Shutdown completed")

# Create FastAPI application
app = FastAPI(
    title=f"{settings.PROJECT_NAME} API",
    description=f"{settings.DESCRIPTION} - Production API with clean architecture",
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)

# Add Security Middleware (production only)
if not settings.DEBUG:
    app.add_middleware(
        TrustedHostMiddleware, 
        allowed_hosts=["trustcheck.com", "*.trustcheck.com", "localhost"]
    )

# Add CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# ======================== DEPENDENCY INJECTION ========================

def get_entity_repository(db: Session = Depends(get_db)) -> EntityRepository:
    """Get entity repository dependency."""
    return EntityRepository(db)

def get_entity_service(
    entity_repo: EntityRepository = Depends(get_entity_repository)
) -> EntityService:
    """Get entity service with injected dependencies."""
    # For now, we'll create a simple version without cache and change repo
    # You can enhance this later
    class SimpleEntityService:
        def __init__(self, entity_repo):
            self.entity_repository = entity_repo
            self.logger = get_logger("service.entity")
        
        def get_entity_statistics(self, source=None):
            return self.entity_repository.get_statistics(source)
    
    return SimpleEntityService(entity_repo)

# ======================== EXCEPTION HANDLERS ========================

@app.exception_handler(TrustCheckError)
async def trustcheck_exception_handler(request: Request, exc: TrustCheckError):
    """Handle TrustCheck business exceptions."""
    logger.error(
        f"TrustCheck error: {exc.message}",
        extra={
            "path": str(request.url.path),
            "method": request.method,
            "error_code": exc.error_code.value,
            "error_id": exc.error_id,
            "details": exc.details
        }
    )
    
    # Map error codes to HTTP status codes
    status_map = {
        ErrorCode.VALIDATION_ERROR: status.HTTP_400_BAD_REQUEST,
        ErrorCode.ENTITY_NOT_FOUND: status.HTTP_404_NOT_FOUND,
        ErrorCode.ENTITY_ALREADY_EXISTS: status.HTTP_409_CONFLICT,
        ErrorCode.DATABASE_CONNECTION_ERROR: status.HTTP_503_SERVICE_UNAVAILABLE,
    }
    
    http_status = status_map.get(exc.error_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return JSONResponse(
        status_code=http_status,
        content=exc.to_dict()
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors."""
    logger.warning(
        f"Validation error on {request.method} {request.url.path}",
        extra={
            "path": str(request.url.path),
            "method": request.method,
            "errors": exc.errors()
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Input validation failed",
                "details": {"validation_errors": exc.errors()},
                "timestamp": datetime.utcnow().isoformat()
            }
        }
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    # Convert to TrustCheckError
    trustcheck_error = handle_exception(exc, context=f"{request.method} {request.url.path}")
    
    logger.error(
        f"Unexpected error: {exc}",
        extra={
            "path": str(request.url.path),
            "method": request.method,
            "error_id": trustcheck_error.error_id,
            "exception_type": type(exc).__name__
        },
        exc_info=True
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=trustcheck_error.to_dict()
    )

# ======================== HEALTH AND MONITORING ENDPOINTS ========================

@app.get("/health")
async def health_check(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Comprehensive health check endpoint."""
    db_healthy = check_db_health()
    
    return {
        "status": "healthy" if db_healthy else "unhealthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.VERSION,
        "service": settings.PROJECT_NAME,
        "environment": "development" if settings.DEBUG else "production",
        "database": {
            "status": "connected" if db_healthy else "disconnected",
            "type": "PostgreSQL"
        },
        "components": {
            "api": "healthy",
            "database": "healthy" if db_healthy else "unhealthy",
            "change_detection": "healthy"
        }
    }

@app.get("/metrics")
async def get_metrics(
    entity_service = Depends(get_entity_service)
) -> Dict[str, Any]:
    """System metrics for monitoring."""
    if not settings.DEBUG:
        raise HTTPException(status_code=404, detail="Not found")
    
    try:
        db_stats = get_db_stats()
        
        # Get entity statistics
        entity_stats = entity_service.get_entity_statistics()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "database": db_stats,
            "entities": entity_stats,
            "scrapers": {
                "registered": len(scraper_registry.list_available_scrapers()),
                "available": scraper_registry.list_available_scrapers()
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to generate metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate metrics: {str(e)}"
        )

# ======================== ROOT ENDPOINTS ========================

@app.get("/")
async def read_root() -> Dict[str, Any]:
    """Root endpoint with API information."""
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "description": settings.DESCRIPTION,
        "status": "operational",
        "timestamp": datetime.utcnow().isoformat(),
        "endpoints": {
            "health": "/health",
            "metrics": "/metrics" if settings.DEBUG else "disabled",
            "documentation": "/docs" if settings.DEBUG else "disabled",
            
            # API endpoints
            "scrape_ofac": "POST /scrape-ofac",
            "search": "GET /search?name={query}",
            "statistics": "GET /stats",
        },
        "features": [
            "Real-time OFAC sanctions data",
            "Automatic change detection", 
            "Clean architecture with dependency injection",
            "Production-grade error handling",
            "Structured logging and monitoring",
            "PostgreSQL database with repositories",
            "Comprehensive test coverage"
        ],
        "architecture": {
            "pattern": "Clean Architecture",
            "layers": ["API", "Services", "Domain", "Infrastructure"],
            "database": "PostgreSQL with Repository Pattern",
            "logging": "Structured logging with context"
        }
    }

# ======================== SCRAPER ENDPOINTS ========================

@app.get("/scrapers")
async def list_scrapers():
    """List all available scrapers with metadata."""
    all_scrapers = scraper_registry.get_all_scrapers()
    available_scrapers = scraper_registry.list_available_scrapers()
    
    return {
        "scrapers": all_scrapers,
        "available_scrapers": available_scrapers,
        "total_count": len(available_scrapers),
        "change_detection_enabled": True,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/scrape/{scraper_name}")
async def scrape_by_name(
    scraper_name: str,
    db: Session = Depends(get_db)
):
    """Generic endpoint to run any registered scraper."""
    
    # Get scraper from registry
    scraper = scraper_registry.create_scraper(scraper_name)
    if not scraper:
        available = scraper_registry.list_available_scrapers()
        raise HTTPException(
            status_code=400,
            detail=f"Unknown scraper: {scraper_name}. Available: {available}"
        )
    
    try:
        logger.info(f"Starting scraping with change detection for {scraper_name}...")
        
        # Run scraper
        result = scraper.scrape_and_store()
        
        if result.status == "SUCCESS":
            return {
                "status": "success",
                "message": f"Successfully scraped {scraper_name}",
                "details": {
                    "source": result.source,
                    "entities_processed": result.entities_processed,
                    "entities_added": result.entities_added,
                    "entities_updated": result.entities_updated,
                    "entities_removed": result.entities_removed,
                    "duration_seconds": result.duration_seconds,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Scraping failed: {result.error_message}"
            )
            
    except Exception as e:
        logger.error(f"Scraping {scraper_name} failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Scraping failed: {str(e)}"
        )

@app.post("/scrape-ofac")
async def scrape_ofac_data(db: Session = Depends(get_db)):
    """Download and process OFAC SDN list with change detection."""
    
    # Get OFAC scraper from registry
    ofac_scraper = scraper_registry.create_scraper("us_ofac")
    if not ofac_scraper:
        raise HTTPException(
            status_code=500, 
            detail="OFAC scraper not found in registry"
        )
    
    try:
        logger.info("Starting OFAC SDN list scraping with change detection...")
        
        # Run scraper
        result = ofac_scraper.scrape_and_store()
        
        if result.status == "SUCCESS":
            logger.info(f"OFAC scraping completed: {result.entities_processed} entities")
            
            return {
                "status": "success",
                "message": f"Successfully processed {result.entities_processed} OFAC entities",
                "details": {
                    "source": result.source,
                    "entities_processed": result.entities_processed,
                    "entities_added": result.entities_added,
                    "entities_updated": result.entities_updated,
                    "entities_removed": result.entities_removed,
                    "duration_seconds": result.duration_seconds,
                    "timestamp": datetime.utcnow().isoformat(),
                    "change_detection_enabled": True
                }
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Scraping failed: {result.error_message}"
            )
            
    except Exception as e:
        logger.error(f"OFAC scraping failed: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Scraping failed: {str(e)}"
        )

# ======================== SEARCH ENDPOINTS ========================

@app.get("/search")
async def search_entities(
    name: str, 
    entity_type: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = 20,
    entity_repo: EntityRepository = Depends(get_entity_repository)
):
    """Search for sanctioned entities."""
    if not name or len(name) < 2:
        raise HTTPException(
            status_code=400, 
            detail="Name must be at least 2 characters"
        )
    
    try:
        # Build filters
        filters = {}
        if entity_type:
            filters['entity_type'] = entity_type.upper()
        if source:
            filters['source'] = source.upper()
        
        # Add name filter
        filters['name'] = f"%{name}%"
        
        entities = entity_repo.get_multi(
            limit=min(limit, 100),
            filters=filters
        )
        
        results = []
        for entity in entities:
            results.append({
                "uid": entity.uid,
                "name": entity.name,
                "type": entity.entity_type,
                "source": entity.source,
                "programs": entity.programs,
                "aliases": (entity.aliases or [])[:3],
                "last_updated": entity.last_seen.isoformat() if entity.last_seen else None
            })
        
        return {
            "query": {"name": name, "entity_type": entity_type, "source": source},
            "results": {"count": len(results), "entities": results},
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )

@app.get("/stats")
async def get_statistics(
    entity_service = Depends(get_entity_service)
):
    """Get comprehensive statistics."""
    try:
        stats = entity_service.get_entity_statistics()
        
        return {
            "entities": stats,
            "change_detection": {
                "status": "operational",
                "features": [
                    "Automatic content hashing",
                    "Real-time change detection",
                    "Risk-based classification"
                ]
            },
            "system": {
                "database": "PostgreSQL",
                "architecture": "Clean Architecture", 
                "environment": "development" if settings.DEBUG else "production"
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Statistics generation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Statistics failed: {str(e)}"
        )

# ======================== APPLICATION ENTRY POINT ========================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )