"""
TrustCheck FastAPI Application

Production-grade API with:
- PostgreSQL integration
- Redis caching
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
from src.database.models import SanctionedEntity, ScrapingLog

# Business logic imports
from src.scrapers.ofac_scraper import OFACScraper

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
    logger.info("🚀 TrustCheck API starting up...")
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
    title=settings.PROJECT_NAME,
    description=settings.DESCRIPTION,
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
    """
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
            "redis": "healthy"  # TODO: Add Redis health check
        }
    }

@app.get("/metrics")
async def get_metrics(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    System metrics for monitoring and alerting.
    """
    if not settings.DEBUG:
        raise HTTPException(status_code=404, detail="Not found")
    
    db_stats = get_db_stats()
    entity_count = db.query(SanctionedEntity).count()
    recent_scrapes = db.query(ScrapingLog).order_by(ScrapingLog.completed_at.desc()).limit(5).all()
    
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
        }
    }

# Root endpoint
@app.get("/")
async def read_root() -> Dict[str, Any]:
    """
    Root endpoint with comprehensive API information.
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
            "scrape_ofac": "POST /scrape-ofac",
            "search": "GET /search?name={query}",
            "statistics": "GET /stats"
        },
        "features": [
            "Real-time OFAC sanctions data",
            "PostgreSQL database",
            "Redis caching",
            "Background job processing",
            "RESTful API",
            "Comprehensive monitoring"
        ]
    }

# Core business endpoints
@app.post("/scrape-ofac")
async def scrape_ofac_data(db: Session = Depends(get_db)):
    """
    Download and process real OFAC SDN list.
    
    This endpoint:
    - Downloads the latest OFAC XML file (~30-60 seconds)
    - Parses 8,000+ sanctioned entities
    - Stores in PostgreSQL database
    - Logs all activity for audit trail
    """
    start_time = time.time()
    
    # Log scraping start
    scraping_log = ScrapingLog(
        source="OFAC",
        status="RUNNING",
        started_at=datetime.utcnow()
    )
    db.add(scraping_log)
    db.commit()
    
    try:
        logger.info("🕷️ Starting OFAC SDN list scraping...")
        
        scraper = OFACScraper()
        entities = scraper.scrape_and_parse()
        
        logger.info(f"📥 Processing {len(entities)} entities...")
        
        # Clear existing OFAC data
        deleted_count = db.query(SanctionedEntity).filter(
            SanctionedEntity.source == "OFAC"
        ).delete()
        
        # Insert new entities
        added_count = 0
        for entity_data in entities:
            db_entity = SanctionedEntity(
                uid=entity_data.uid,
                name=entity_data.name,
                entity_type=entity_data.entity_type,
                source=entity_data.source,
                programs=entity_data.programs,
                aliases=entity_data.aliases,
                addresses=entity_data.addresses,
                dates_of_birth=entity_data.dates_of_birth,
                places_of_birth=entity_data.places_of_birth,
                nationalities=entity_data.nationalities,
                remarks=entity_data.remarks,
                last_seen=entity_data.last_updated
            )
            db.add(db_entity)
            added_count += 1
        
        db.commit()
        
        # Update scraping log
        duration = int(time.time() - start_time)
        scraping_log.status = "SUCCESS"
        scraping_log.entities_processed = len(entities)
        scraping_log.entities_added = added_count
        scraping_log.entities_removed = deleted_count
        scraping_log.completed_at = datetime.utcnow()
        scraping_log.duration_seconds = duration
        db.commit()
        
        logger.info(f"✅ OFAC scraping completed: {added_count} entities added in {duration}s")
        
        return {
            "status": "success",
            "message": f"Successfully scraped and stored {added_count} OFAC entities",
            "details": {
                "entities_processed": len(entities),
                "entities_added": added_count,
                "entities_removed": deleted_count,
                "duration_seconds": duration,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
    except Exception as e:
        # Update scraping log with error
        scraping_log.status = "FAILED"
        scraping_log.error_message = str(e)
        scraping_log.completed_at = datetime.utcnow()
        scraping_log.duration_seconds = int(time.time() - start_time)
        db.commit()
        
        logger.error(f"❌ OFAC scraping failed: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Scraping failed: {str(e)}"
        )

@app.get("/search")
async def search_entities(
    name: str, 
    entity_type: str = None,
    source: str = None,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """
    Search for sanctioned entities with advanced filtering.
    
    Args:
        name: Name to search for (minimum 2 characters)
        entity_type: Filter by entity type (PERSON, COMPANY, etc.)
        source: Filter by data source (OFAC, UN, etc.)
        limit: Maximum results to return (1-100)
    """
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
            "last_updated": entity.last_seen.isoformat() if entity.last_seen else None
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
    
    # Recent scraping activity
    recent_scrapes = db.query(ScrapingLog).order_by(
        ScrapingLog.completed_at.desc()
    ).limit(5).all()
    
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
        "system": {
            "database": "PostgreSQL",
            "cache": "Redis",
            "environment": "development" if settings.DEBUG else "production"
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