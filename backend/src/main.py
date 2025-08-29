"""
TrustCheck API - Async Only
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import datetime
import uuid

from src.core.config import settings
from src.core.logging_config import get_logger
from src.infrastructure.database.connection import init_db, close_db
from src.api.change_detection import router as api_router

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    logger.info(f"Starting {settings.project_name} v{settings.version}")
    await init_db()
    yield
    await close_db()
    logger.info("Shutting down application")

app = FastAPI(
    title=settings.project_name,
    description=settings.description,
    version=settings.version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add request ID to all requests."""
    request.state.request_id = str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response

app.include_router(api_router)

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    from src.infrastructure.database.connection import db_manager
    db_healthy = await db_manager.check_connection()
    
    return {
        "status": "healthy" if db_healthy else "degraded",
        "version": settings.version,
        "timestamp": datetime.utcnow().isoformat(),
        "database": "connected" if db_healthy else "disconnected"
    }

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.project_name,
        "version": settings.version,
        "description": settings.description,
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "entities": "/api/v1/entities",
            "changes": "/api/v1/changes",
            "statistics": "/api/v1/statistics"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )