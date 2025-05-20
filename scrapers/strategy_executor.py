from base_scraper import BaseScraper

def run_scraper(scraper: BaseScraper):
    try:
        return scraper.scrape()
    except Exception as e:
        print(f"Error al scrapear con {scraper.__class__.__name__}: {e}")
        return []