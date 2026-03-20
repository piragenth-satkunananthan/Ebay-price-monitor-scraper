import time
from scraper import main as scrape_all_prices

INTERVAL_SECONDS = 60

if __name__ == "__main__":
    print("Starting background eBay scraper...")
    while True:
        try:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Scraping latest prices...")
            scrape_all_prices()
            print("Scraping complete. Going to sleep.")
        except Exception as e:
            print(f" Error during scraping: {e}")
        
        time.sleep(INTERVAL_SECONDS)
