"""
TrustCheck API - Production Application with API Versioning

Includes both v1 (backward compatibility) and v2 (production) endpoints.
"""
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from datetime import datetime
import uuid

from src.core.config import settings
from src.core.logging_config import get_logger
from src.infrastructure.database.connection import init_db, close_db
from src.core.exceptions import TrustCheckError, create_error_response

# Import both API versions
from src.api.change_detection import router as v1_router
from src.api.v2.change_detection import router as v2_router

logger = get_logger(__name__)

# ======================== LIFESPAN MANAGEMENT ========================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    logger.info(f"Starting {settings.project_name} v{settings.version}")
    await init_db()
    yield
    await close_db()
    logger.info("Shutting down application")

# ======================== APPLICATION SETUP ========================

app = FastAPI(
    title=settings.project_name,
    description=f"{settings.description}\n\n"
                f"**API Versions:**\n"
                f"- v1: Legacy API (deprecated, for backward compatibility)\n"
                f"- v2: Production API with DTOs and validation (recommended)",
    version=settings.version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ======================== MIDDLEWARE ========================

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.security.allowed_origins if hasattr(settings, 'security') else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add request ID to all requests."""
    request.state.request_id = str(uuid.uuid4())
    
    # Log request
    logger.info(f"Request: {request.method} {request.url.path}")
    
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    
    # Add API deprecation warning for v1
    if "/api/v1/" in str(request.url):
        response.headers["X-API-Deprecation-Warning"] = "API v1 is deprecated. Please migrate to v2."
    
    return response

# ======================== ERROR HANDLERS ========================

@app.exception_handler(TrustCheckError)
async def trustcheck_error_handler(request: Request, exc: TrustCheckError):
    """Handle custom application errors."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=create_error_response(exc)
    )

@app.exception_handler(Exception)
async def global_error_handler(request: Request, exc: Exception):
    """Handle unexpected errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "request_id": getattr(request.state, 'request_id', None)
            }
        }
    )

# ======================== INCLUDE ROUTERS ========================

# Include v1 API (deprecated, for backward compatibility)
app.include_router(
    v1_router,
    prefix="",
    tags=["API v1 (Deprecated)"],
    deprecated=True  # Mark as deprecated in OpenAPI docs
)

# Include v2 API (production, recommended)
app.include_router(
    v2_router,
    prefix="",
    tags=["API v2 (Production)"]
)

# ======================== ROOT ENDPOINTS ========================

@app.get("/", tags=["System"])
async def root():
    """API information and version endpoints."""
    return {
        "name": settings.project_name,
        "version": settings.version,
        "description": settings.description,
        "api_versions": {
            "v1": {
                "status": "deprecated",
                "base_url": "/api/v1",
                "message": "Legacy API, will be removed in future version"
            },
            "v2": {
                "status": "production",
                "base_url": "/api/v2",
                "message": "Current production API with full validation"
            }
        },
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc"
        },
        "endpoints": {
            "health": "/health",
            "v1_entities": "/api/v1/entities",
            "v2_entities": "/api/v2/entities",
            "v1_changes": "/api/v1/changes",
            "v2_changes": "/api/v2/changes"
        }
    }

@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint."""
    from src.infrastructure.database.connection import db_manager
    
    db_healthy = await db_manager.check_connection()
    
    return {
        "status": "healthy" if db_healthy else "degraded",
        "version": settings.version,
        "environment": settings.environment.value if hasattr(settings, 'environment') else "production",
        "api_versions": ["v1 (deprecated)", "v2 (production)"],
        "timestamp": datetime.utcnow().isoformat(),
        "database": "connected" if db_healthy else "disconnected"
    }

@app.get("/api", tags=["System"])
async def api_versions():
    """List available API versions."""
    return {
        "versions": [
            {
                "version": "v1",
                "status": "deprecated",
                "base_url": "/api/v1",
                "deprecation_date": "2025-09-01",
                "sunset_date": "2025-12-01",
                "migration_guide": "https://docs.trustcheck.com/migration/v1-to-v2"
            },
            {
                "version": "v2",
                "status": "production",
                "base_url": "/api/v2",
                "released": "2025-08-01",
                "features": [
                    "Full DTO validation",
                    "Comprehensive error handling",
                    "Type-safe responses",
                    "Better performance"
                ]
            }
        ],
        "recommended": "v2",
        "documentation": "/docs"
    }

# ======================== MAIN ========================

if __name__ == "__main__":
    import uvicorn
    
    # Determine reload based on environment
    reload = settings.environment.value != "production" if hasattr(settings, 'environment') else True
    
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=reload,
        log_level=settings.observability.log_level.value.lower() if hasattr(settings, 'observability') else "info"
    )