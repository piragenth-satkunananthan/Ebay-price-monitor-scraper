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

Product Search uses headed Chromium. Docker runs Streamlit under `xvfb-run`,
which supplies a virtual display without opening a desktop window. Keep this
wrapper when changing the container command: headless Firefox and Chromium
returned eBay error/verification pages during access checks, while headed
Chromium returned listings. eBay can still require verification or refuse access.

For local development with a desktop display, run
`uv run --python 3.12 streamlit run main.py`. On a Linux server without a desktop,
use `xvfb-run -a uv run --python 3.12 streamlit run main.py`.

Run the offline regression tests in the frontend container with:

```bash
docker exec ebay_frontend xvfb-run -a /app/.venv/bin/python -m unittest discover -s tests -v
```

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
