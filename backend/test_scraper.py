import asyncio
from src.scrapers.us.ofac.scraper import OFACScraper

async def test_scraper():
    scraper = OFACScraper()
    result = await scraper.scrape_and_store()
    print(f"Scraping result: {result}")

asyncio.run(test_scraper())