"""
TrustCheck API Routes.

All API route modules.
"""

from trustcheck.api.routes.admin import router as admin_router
from trustcheck.api.routes.audit import router as audit_router
from trustcheck.api.routes.batch import router as batch_router
from trustcheck.api.routes.changes import router as changes_router
from trustcheck.api.routes.entities import router as entities_router
from trustcheck.api.routes.health import router as health_router
from trustcheck.api.routes.screening import router as screening_router
from trustcheck.api.routes.search import router as search_router
from trustcheck.api.routes.watchlists import alerts_router, router as watchlists_router
from trustcheck.api.routes.websocket import router as websocket_router

__all__ = [
    "admin_router",
    "alerts_router",
    "audit_router",
    "batch_router",
    "changes_router",
    "entities_router",
    "health_router",
    "screening_router",
    "search_router",
    "watchlists_router",
    "websocket_router",
]
