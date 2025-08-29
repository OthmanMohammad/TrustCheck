from src.scrapers.us.ofac.scraper import OFACScraper

# Test OFAC scraper with change detection
scraper = OFACScraper()
result = scraper.scrape_and_store()
print(f"Entities processed: {result.entities_processed}")
print(f"Status: {result.status}")