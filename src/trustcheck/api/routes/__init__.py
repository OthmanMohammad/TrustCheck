"""
TrustCheck API Routes.

All API route modules.
"""

from trustcheck.api.routes.admin import router as admin_router
from trustcheck.api.routes.changes import router as changes_router
from trustcheck.api.routes.entities import router as entities_router
from trustcheck.api.routes.health import router as health_router
from trustcheck.api.routes.screening import router as screening_router

__all__ = [
    "admin_router",
    "changes_router",
    "entities_router",
    "health_router",
    "screening_router",
]
