import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent / 'backend'))

async def run():
    print("Starting OFAC Scraper...")
    
    # Import after path is set
    from src.scrapers.us.ofac.scraper import OFACScraper
    from src.infrastructure.database.connection import init_db, close_db
    
    # Initialize database
    await init_db()
    
    try:
        # Create and run scraper
        scraper = OFACScraper()
        result = await scraper.scrape_and_store()
        
        print(f"\nStatus: {result.status}")
        print(f"Entities: {result.entities_processed}")
        print(f"Added: {result.entities_added}")
        print(f"Updated: {result.entities_updated}") 
        print(f"Duration: {result.duration_seconds:.1f}s")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await close_db()

if __name__ == "__main__":
    asyncio.run(run())