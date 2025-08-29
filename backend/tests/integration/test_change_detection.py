import asyncio
from src.services.change_detection.service import ChangeDetectionService
from src.infrastructure.database.uow import get_uow_factory
from src.core.enums import DataSource

async def test_change_detection():
    uow_factory = get_uow_factory()
    service = ChangeDetectionService(uow_factory)
    
    summary = await service.get_change_summary(
        days=7,
        source=DataSource.OFAC
    )
    print(f"Change summary: {summary}")
    
    critical = await service.get_critical_changes(
        hours=24,
        source=DataSource.OFAC
    )
    print(f"Critical changes: {len(critical)}")

asyncio.run(test_change_detection())