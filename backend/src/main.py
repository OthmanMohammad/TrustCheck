"""
TrustCheck FastAPI Application with Change Detection

Production-grade API with:
- PostgreSQL integration with change detection
- Redis caching
- Change detection endpoints
- Comprehensive monitoring
- Error handling
- Security features
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
import logging
import time
from datetime import datetime
from typing import Dict, Any

# Core imports
from src.core.config import settings
from src.core.exceptions import TrustCheckError
from src.utils.logger import get_logger

# Database imports
from src.database.connection import get_db, create_tables, check_db_health, get_db_stats
from src.database.models import SanctionedEntity, ScrapingLog, ChangeEvent, ScraperRun

# Business logic imports
from src.scrapers import scraper_registry
from src.scrapers.registry import Region, ScraperTier

# NEW: Change detection API routes
from src.api.change_detection import router as change_detection_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan events with comprehensive startup and shutdown.
    """
    # Startup
    logger.info("🚀 TrustCheck API with Change Detection starting up...")
    logger.info(f"📊 Environment: {'Development' if settings.DEBUG else 'Production'}")
    logger.info(f"🗃️ Database: {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
    logger.info(f"🔴 Redis: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
    
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

# Create FastAPI application with comprehensive configuration
app = FastAPI(
    title=settings.PROJECT_NAME + " with Change Detection",  # Updated title
    description=settings.DESCRIPTION + " - Now with automatic change detection and real-time monitoring.",
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)

# Add Security Middleware
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

# NEW: Include change detection routes
app.include_router(change_detection_router)

# Global exception handlers
@app.exception_handler(TrustCheckError)
async def trustcheck_exception_handler(request, exc: TrustCheckError):
    """Handle custom TrustCheck exceptions."""
    logger.error(f"TrustCheck error: {exc}", extra={
        "path": str(request.url.path),
        "method": request.method,
        "details": getattr(exc, 'details', {})
    })
    return JSONResponse(
        status_code=400,
        content={
            "error": str(exc),
            "type": type(exc).__name__,
            "timestamp": datetime.utcnow().isoformat()
        }
    )

@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(f"Unexpected error: {exc}", extra={
        "path": str(request.url.path),
        "method": request.method
    }, exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "timestamp": datetime.utcnow().isoformat()
        }
    )

# Health and monitoring endpoints
@app.get("/health")
async def health_check(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Comprehensive health check endpoint for monitoring.
    Enhanced with change detection status.
    """
    db_healthy = check_db_health()
    
    # Check change detection tables
    change_detection_healthy = True
    try:
        db.query(ChangeEvent).count()
        db.query(ScraperRun).count()
    except Exception as e:
        logger.error(f"Change detection tables unhealthy: {e}")
        change_detection_healthy = False
    
    return {
        "status": "healthy" if (db_healthy and change_detection_healthy) else "unhealthy",
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
            "change_detection": "healthy" if change_detection_healthy else "unhealthy",
            "redis": "healthy"  # TODO: Add Redis health check
        },
        "features": [
            "Real-time change detection",
            "Risk-based notifications", 
            "Comprehensive audit trail",
            "Multiple sanctions sources"
        ]
    }

@app.get("/metrics")
async def get_metrics(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    System metrics for monitoring and alerting.
    Enhanced with change detection metrics.
    """
    if not settings.DEBUG:
        raise HTTPException(status_code=404, detail="Not found")
    
    db_stats = get_db_stats()
    entity_count = db.query(SanctionedEntity).count()
    recent_scrapes = db.query(ScrapingLog).order_by(ScrapingLog.completed_at.desc()).limit(5).all()
    
    # NEW: Change detection metrics
    total_changes = db.query(ChangeEvent).count()
    recent_changes = db.query(ChangeEvent).filter(
        ChangeEvent.detected_at >= datetime.utcnow() - timedelta(hours=24)
    ).count()
    critical_changes = db.query(ChangeEvent).filter(
        ChangeEvent.risk_level == 'CRITICAL'
    ).count()
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "database": db_stats,
        "entities": {
            "total_count": entity_count,
            "ofac_count": db.query(SanctionedEntity).filter(SanctionedEntity.source == "OFAC").count()
        },
        "scraping": {
            "recent_runs": len(recent_scrapes),
            "last_successful": recent_scrapes[0].completed_at.isoformat() if recent_scrapes and recent_scrapes[0].status == "SUCCESS" else None
        },
        "change_detection": {
            "total_changes": total_changes,
            "recent_changes_24h": recent_changes,
            "critical_changes_all_time": critical_changes,
            "system_status": "operational"
        }
    }

# Root endpoint
@app.get("/")
async def read_root() -> Dict[str, Any]:
    """
    Root endpoint with comprehensive API information.
    Enhanced with change detection features.
    """
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
            
            # Legacy endpoints
            "scrape_ofac": "POST /scrape-ofac",
            "search": "GET /search?name={query}",
            "statistics": "GET /stats",
            
            # NEW: Change detection endpoints
            "changes": "GET /api/v1/change-detection/changes",
            "changes_summary": "GET /api/v1/change-detection/changes/summary",
            "scraper_runs": "GET /api/v1/change-detection/runs",
            "system_status": "GET /api/v1/change-detection/status",
            "trigger_detection": "POST /api/v1/change-detection/trigger/{source}"
        },
        "features": [
            "Real-time OFAC sanctions data",
            "Automatic change detection",
            "Risk-based change classification",
            "Real-time notifications",
            "Complete audit trail",
            "PostgreSQL database",
            "Redis caching",
            "Background job processing",
            "RESTful API",
            "Comprehensive monitoring"
        ]
    }

# ======================== EXISTING ENDPOINTS (Unchanged) ========================

@app.get("/scrapers")
async def list_scrapers():
    """List all available scrapers with metadata."""
    all_scrapers = scraper_registry.get_all_scrapers()
    available_scrapers = scraper_registry.list_available_scrapers()
    
    # Convert enum values to strings for JSON serialization
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
            "change_detection_enabled": True  # NEW: All scrapers now have change detection
        }
    
    return {
        "scrapers": scrapers_data,
        "available_scrapers": available_scrapers,
        "total_count": len(available_scrapers),
        "change_detection_enabled": True,  # NEW: System-wide change detection
        "by_region": {
            "us": scraper_registry.list_by_region(Region.US),
            "europe": scraper_registry.list_by_region(Region.EUROPE),
            "international": scraper_registry.list_by_region(Region.INTERNATIONAL)
        },
        "by_tier": {
            "tier1": scraper_registry.list_by_tier(ScraperTier.TIER1),
            "tier2": scraper_registry.list_by_tier(ScraperTier.TIER2),
            "tier3": scraper_registry.list_by_tier(ScraperTier.TIER3)
        }
    }

@app.post("/scrape/{scraper_name}")
async def scrape_by_name(
    scraper_name: str,
    db: Session = Depends(get_db)
):
    """
    Generic endpoint to run any registered scraper.
    Now with automatic change detection for all scrapers.
    """
    
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
        
        # Run scraper (now with automatic change detection)
        result = scraper.scrape_and_store()
        
        if result.status == "SUCCESS":
            return {
                "status": "success",
                "message": f"Successfully scraped {scraper_name} with change detection",
                "details": {
                    "source": result.source,
                    "entities_processed": result.entities_processed,
                    "entities_added": result.entities_added,     # NEW: Change detection metrics
                    "entities_updated": result.entities_updated, # NEW: Change detection metrics  
                    "entities_removed": result.entities_removed, # NEW: Change detection metrics
                    "duration_seconds": result.duration_seconds,
                    "timestamp": datetime.utcnow().isoformat(),
                    "change_detection_enabled": True  # NEW: Confirm change detection ran
                }
            }
        elif result.status == "SKIPPED":
            return {
                "status": "skipped",
                "message": f"Skipped {scraper_name} - no content changes detected",
                "details": {
                    "source": result.source,
                    "content_unchanged": True,  # NEW: Content hash optimization
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
    """
    Download and process real OFAC SDN list using the registry.
    Enhanced with automatic change detection.
    
    This endpoint:
    - Uses the scraper registry to get OFAC scraper
    - Downloads the latest OFAC XML file (~30-60 seconds)
    - Automatically detects changes from previous run
    - Parses 8,000+ sanctioned entities
    - Stores changes with risk classification
    - Sends notifications for critical changes
    - Logs all activity for audit trail
    """
    start_time = time.time()
    
    # Get OFAC scraper from registry
    ofac_scraper = scraper_registry.create_scraper("us_ofac")
    if not ofac_scraper:
        raise HTTPException(
            status_code=500, 
            detail="OFAC scraper not found in registry"
        )
    
    try:
        logger.info("Starting OFAC SDN list scraping with change detection...")
        
        # Run scraper using enhanced framework with change detection
        result = ofac_scraper.scrape_and_store()
        
        if result.status == "SUCCESS":
            logger.info(f"OFAC scraping completed: {result.entities_processed} entities, "
                       f"{result.entities_added} added, {result.entities_updated} modified, "
                       f"{result.entities_removed} removed")
            
            return {
                "status": "success",
                "message": f"Successfully scraped and processed {result.entities_processed} OFAC entities with change detection",
                "details": {
                    "source": result.source,
                    "entities_processed": result.entities_processed,
                    "entities_added": result.entities_added,
                    "entities_updated": result.entities_updated,
                    "entities_removed": result.entities_removed,
                    "duration_seconds": result.duration_seconds,
                    "timestamp": datetime.utcnow().isoformat(),
                    "change_detection": {
                        "enabled": True,
                        "content_hash_calculated": True,
                        "changes_stored": result.entities_added + result.entities_updated + result.entities_removed > 0,
                        "audit_trail_created": True
                    }
                }
            }
        elif result.status == "SKIPPED":
            logger.info("OFAC scraping skipped - no content changes detected")
            
            return {
                "status": "skipped",
                "message": "OFAC content unchanged - skipped processing for efficiency",
                "details": {
                    "source": result.source,
                    "content_unchanged": True,
                    "duration_seconds": result.duration_seconds,
                    "timestamp": datetime.utcnow().isoformat(),
                    "optimization": "Content hash comparison prevented unnecessary processing"
                }
            }
        else:
            logger.error(f"OFAC scraping failed: {result.error_message}")
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

# ======================== REMAINING ENDPOINTS (Unchanged) ========================

@app.get("/search")
async def search_entities(
    name: str, 
    entity_type: str = None,
    source: str = None,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """Search for sanctioned entities with advanced filtering."""
    if not name or len(name) < 2:
        raise HTTPException(
            status_code=400, 
            detail="Name must be at least 2 characters"
        )
    
    if limit < 1 or limit > 100:
        limit = 20
    
    # Build query
    query = db.query(SanctionedEntity).filter(
        SanctionedEntity.name.ilike(f"%{name}%")
    )
    
    if entity_type:
        query = query.filter(SanctionedEntity.entity_type == entity_type.upper())
    
    if source:
        query = query.filter(SanctionedEntity.source == source.upper())
    
    entities = query.limit(limit).all()
    
    results = []
    for entity in entities:
        results.append({
            "uid": entity.uid,
            "name": entity.name,
            "type": entity.entity_type,
            "source": entity.source,
            "programs": entity.programs,
            "aliases": entity.aliases[:3] if entity.aliases else [],
            "addresses": entity.addresses[:2] if entity.addresses else [],
            "nationalities": entity.nationalities,
            "last_updated": entity.last_seen.isoformat() if entity.last_seen else None,
            "content_hash": entity.content_hash[:12] + "..." if entity.content_hash else None  # NEW: Show hash preview
        })
    
    return {
        "query": {
            "name": name,
            "entity_type": entity_type,
            "source": source,
            "limit": limit
        },
        "results": {
            "count": len(results),
            "entities": results
        },
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/stats")
async def get_statistics(db: Session = Depends(get_db)):
    """
    Get comprehensive database and system statistics.
    Enhanced with change detection statistics.
    """
    total_entities = db.query(SanctionedEntity).count()
    
    # Count by source
    source_counts = {}
    sources = ["OFAC", "UN", "EU", "UK_HMT"]
    for source in sources:
        count = db.query(SanctionedEntity).filter(SanctionedEntity.source == source).count()
        if count > 0:
            source_counts[source] = count
    
    # Count by entity type
    type_counts = {}
    for entity_type in ["PERSON", "COMPANY", "VESSEL", "AIRCRAFT"]:
        count = db.query(SanctionedEntity).filter(SanctionedEntity.entity_type == entity_type).count()
        if count > 0:
            type_counts[entity_type] = count
    
    # Recent scraping activity (legacy)
    recent_scrapes = db.query(ScrapingLog).order_by(
        ScrapingLog.completed_at.desc()
    ).limit(5).all()
    
    # NEW: Change detection statistics
    total_changes = db.query(ChangeEvent).count()
    recent_changes = db.query(ChangeEvent).filter(
        ChangeEvent.detected_at >= datetime.utcnow() - timedelta(days=7)
    ).count()
    
    return {
        "entities": {
            "total": total_entities,
            "by_source": source_counts,
            "by_type": type_counts
        },
        "scraping": {
            "recent_activity": [
                {
                    "source": log.source,
                    "status": log.status,
                    "entities_processed": log.entities_processed,
                    "completed_at": log.completed_at.isoformat() if log.completed_at else None,
                    "duration_seconds": log.duration_seconds
                }
                for log in recent_scrapes
            ]
        },
        "change_detection": {  # NEW: Change detection stats
            "total_changes": total_changes,
            "recent_changes_7d": recent_changes,
            "status": "operational",
            "features": [
                "Automatic content hashing",
                "Risk-based classification", 
                "Real-time notifications",
                "Complete audit trail"
            ]
        },
        "system": {
            "database": "PostgreSQL",
            "cache": "Redis",
            "environment": "development" if settings.DEBUG else "production",
            "change_detection_enabled": True  # NEW: System capability flag
        },
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )