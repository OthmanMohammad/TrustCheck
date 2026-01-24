"""
TrustCheck Web UI Module.

Server-side rendered web interface using Jinja2 templates.
"""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from trustcheck.config import settings
from trustcheck.database import (
    ChangeEventRepository,
    DashboardRepository,
    EntityRepository,
    get_session_context,
)
from trustcheck.domain import DataSource, ScreeningRequest
from trustcheck.services import get_screening_service

# Templates directory
TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(tags=["Web UI"])


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    """Dashboard page."""
    async with get_session_context() as session:
        repo = DashboardRepository(session)
        stats = await repo.get_stats()

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "stats": stats,
            "settings": settings,
        },
    )


@router.get("/entities", response_class=HTMLResponse)
async def entities_list(
    request: Request,
    source: str | None = None,
    entity_type: str | None = None,
    page: int = 1,
) -> HTMLResponse:
    """Entities list page."""
    limit = 50
    offset = (page - 1) * limit

    source_filter = None
    if source:
        try:
            source_filter = DataSource(source.upper())
        except ValueError:
            pass

    type_filter = None
    if entity_type:
        from trustcheck.domain import EntityType

        try:
            type_filter = EntityType(entity_type.upper())
        except ValueError:
            pass

    async with get_session_context() as session:
        repo = EntityRepository(session)
        entities, total = await repo.list_entities(
            source=source_filter,
            entity_type=type_filter,
            active_only=True,
            limit=limit,
            offset=offset,
        )

    total_pages = (total + limit - 1) // limit

    return templates.TemplateResponse(
        "entities.html",
        {
            "request": request,
            "entities": entities,
            "total": total,
            "page": page,
            "total_pages": total_pages,
            "source": source,
            "entity_type": entity_type,
            "settings": settings,
        },
    )


@router.get("/entities/{entity_id}", response_class=HTMLResponse)
async def entity_detail(request: Request, entity_id: str) -> HTMLResponse:
    """Entity detail page."""
    async with get_session_context() as session:
        repo = EntityRepository(session)
        entity = await repo.get_by_id(entity_id)

    if not entity:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "Entity not found",
                "settings": settings,
            },
            status_code=404,
        )

    return templates.TemplateResponse(
        "entity_detail.html",
        {
            "request": request,
            "entity": entity,
            "settings": settings,
        },
    )


@router.get("/screening", response_class=HTMLResponse)
async def screening_page(request: Request) -> HTMLResponse:
    """Screening page."""
    return templates.TemplateResponse(
        "screening.html",
        {
            "request": request,
            "settings": settings,
        },
    )


@router.post("/screening", response_class=HTMLResponse)
async def screening_submit(request: Request) -> HTMLResponse:
    """Handle screening form submission."""
    form = await request.form()
    name = form.get("name", "")
    threshold = float(form.get("threshold", 0.8))

    results = None
    if name:
        service = get_screening_service()
        screen_request = ScreeningRequest(
            name=str(name),
            threshold=threshold,
            max_results=50,
        )
        results = await service.screen(screen_request)

    return templates.TemplateResponse(
        "screening.html",
        {
            "request": request,
            "name": name,
            "threshold": threshold,
            "results": results,
            "settings": settings,
        },
    )


@router.get("/changes", response_class=HTMLResponse)
async def changes_page(request: Request, days: int = 7, page: int = 1) -> HTMLResponse:
    """Changes monitoring page."""
    limit = 50
    offset = (page - 1) * limit

    async with get_session_context() as session:
        repo = ChangeEventRepository(session)
        changes, total = await repo.list_changes(
            days=days,
            limit=limit,
            offset=offset,
        )

    total_pages = (total + limit - 1) // limit

    return templates.TemplateResponse(
        "changes.html",
        {
            "request": request,
            "changes": changes,
            "total": total,
            "days": days,
            "page": page,
            "total_pages": total_pages,
            "settings": settings,
        },
    )


@router.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request) -> HTMLResponse:
    """Admin page."""
    from trustcheck.database import ScraperRunRepository
    from trustcheck.scheduler import get_job_status, get_scheduler

    async with get_session_context() as session:
        repo = ScraperRunRepository(session)
        latest_runs = await repo.get_all_latest()

    scheduler = get_scheduler()
    scheduler_running = scheduler.running if scheduler else False
    jobs = get_job_status() if scheduler_running else []

    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "latest_runs": latest_runs,
            "scheduler_running": scheduler_running,
            "jobs": jobs,
            "settings": settings,
        },
    )


__all__ = ["router", "templates"]
