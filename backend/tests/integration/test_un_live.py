# force_un_scrape.py
import asyncio
from src.scrapers.international.un.scraper import UNScraper

async def force_scrape():
    scraper = UNScraper()
    
    # Clear any cached content hash first
    from src.infrastructure.database.connection import db_manager
    from sqlalchemy import text
    
    async with db_manager.get_session() as session:
        # Clear UN scraper runs to force processing
        await session.execute(
            text("DELETE FROM scraper_runs WHERE source = 'un'")
        )
        await session.commit()
    
    # Now run the scraper
    print("Force running UN scraper...")
    result = await scraper.scrape_and_store()
    print(f"Result: {result.status}")
    print(f"Entities: {result.entities_processed}")
    
asyncio.run(force_scrape())