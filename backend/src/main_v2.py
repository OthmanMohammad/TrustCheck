"""
Main Application Entry Point - V2 with DTOs

Production-grade FastAPI application with:
- Request/Response validation
- OpenAPI documentation
- Error handling
- Health checks
"""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import uvicorn

from src.core.config import settings
from src.core.logging_config import setup_logging, get_logger
from src.core.exceptions import TrustCheckError, create_error_response

# Import both API versions
from src.api.change_detection import router as v1_router
from src.api.v2.change_detection import router as v2_router

# Import schema customization
from src.api.schemas import customize_openapi_schema

logger = get_logger(__name__)

# ======================== LIFESPAN MANAGEMENT ========================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Startup
    logger.info(f"Starting {settings.project_name} v{settings.version}")
    setup_logging()
    
    # Initialize database connections
    from src.infrastructure.database.connection import init_db
    await init_db()
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")
    # Cleanup connections
    from src.infrastructure.database.connection import close_db
    await close_db()

# ======================== APPLICATION SETUP ========================

app = FastAPI(
    title=settings.project_name,
    description=settings.description,
    version=settings.version,
    lifespan=lifespan,
    docs_url="/api/docs" if settings.docs_enabled else None,
    redoc_url="/api/redoc" if settings.docs_enabled else None,
)

# ======================== MIDDLEWARE ========================

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.security.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add request ID to all requests."""
    import uuid
    from src.core.logging_config import LoggingContext
    
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    with LoggingContext(request_id=request_id):
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
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

# ======================== ROUTERS ========================

# Include v1 API (without DTOs)
app.include_router(v1_router, prefix="", tags=["API v1 (Legacy)"])

# Include v2 API (with DTOs and validation)
app.include_router(v2_router, prefix="", tags=["API v2 (Production)"])

# ======================== HEALTH CHECK ========================

@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": settings.version,
        "environment": settings.environment.value
    }

# ======================== ROOT ENDPOINT ========================

@app.get("/", tags=["System"])
async def root():
    """API information endpoint."""
    return {
        "name": settings.project_name,
        "version": settings.version,
        "description": settings.description,
        "documentation": {
            "swagger": "/api/docs",
            "redoc": "/api/redoc",
            "v1_endpoints": "/api/v1",
            "v2_endpoints": "/api/v2"
        }
    }

# ======================== OPENAPI CUSTOMIZATION ========================

def custom_openapi():
    """Customize OpenAPI schema."""
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = app.openapi()
    app.openapi_schema = customize_openapi_schema(openapi_schema)
    return app.openapi_schema

app.openapi = custom_openapi

# ======================== MAIN ========================

if __name__ == "__main__":
    uvicorn.run(
        "src.main_v2:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.observability.log_level.value.lower()
    )