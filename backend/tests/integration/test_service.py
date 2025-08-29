import asyncio
from src.services.change_detection.service import ChangeDetectionService
from src.infrastructure.database.uow import get_uow_factory
from src.core.enums import DataSource

async def test_change_detection():
    uow_factory = get_uow_factory()
    service = ChangeDetectionService(uow_factory)
    
    # Test get_change_summary
    summary = await service.get_change_summary(days=7)
    print(f"Change summary: {summary}")
    
    # Test get_critical_changes
    critical = await service.get_critical_changes(hours=24)
    print(f"Critical changes: {len(critical)}")

if __name__ == "__main__":
    asyncio.run(test_change_detection())