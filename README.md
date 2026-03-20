# eBay Price Monitor & Scraper

A tool that scrapes eBay product listings, tracks prices , and displays price history .

---


## 🗂️ Project Structure

```
Ebay-price-monitor-scraper/
├── main.py               # Streamlit UI entry point
├── product_search.py     # Playwright-based eBay search scraper
├── scraper.py            # Per-product price scraper (used by the worker)
├── run_scraper.py        # Background worker — loops and re-scrapes all monitored products
├── database.py           # SQLite helpers (add product, log price, fetch history)
├── db_test.py            # Manual DB testing script
├── Dockerfile            # Container image definition
├── docker-compose.yml    # Defines frontend + scraper services
├── pyproject.toml        # Python project config (uv)
├── uv.lock               # Locked dependency versions
└── .python-version       # Pins Python 3.12
```

---




```bash
git clone https://github.com/piragenth-satkunananthan/Ebay-price-monitor-scraper.git
cd Ebay-price-monitor-scraper
docker compose up --build
```

using uv is recommended

The SQLite database file is mounted as a volume so data persists between restarts.

---


Open `http://localhost:8501` in your browser.

---




## Key Dependencies

```toml
streamlit
playwright
pandas
plotly
python3.12
```

All versions are pinned in `uv.lock`. Run `uv sync` to install the exact locked versions.




## 📄 License

This project is open source. See the repository for details.

## Contact me for any tool you need