import time
from scraper import main as scrape_all_prices

INTERVAL_SECONDS = 60 * 60 * 10

if __name__ == "__main__":
    print("Starting background eBay scraper...",flush=True)
    while True:
        try:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Scraping latest prices...",flush=True)
            scrape_all_prices()
            print("Scraping complete. Going to sleep.",flush=True)
        except Exception as e:
            print(f" Error during scraping: {e}",flush=True)
        
        time.sleep(INTERVAL_SECONDS)
