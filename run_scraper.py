import time
import logging
from scraper import main as scrape_all_prices

INTERVAL_SECONDS = 60 * 60 * 10

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print("Starting background eBay scraper...",flush=True)
    while True:
        try:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Scraping latest prices...",flush=True)
            completed = scrape_all_prices()
            if completed:
                print("Scraping complete. Going to sleep.",flush=True)
            else:
                print("Scraping stopped because eBay refused access. Going to sleep.",flush=True)
        except Exception as e:
            print(f" Error during scraping: {e}",flush=True)
        
        time.sleep(INTERVAL_SECONDS)
