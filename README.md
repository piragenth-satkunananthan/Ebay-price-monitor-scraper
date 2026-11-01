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

Each service reuses its own Chromium profile in `.browser-state/`, separated by
Playwright version so upgrades start with a compatible profile. Keep the profile
directories private and out of Git. A shared file lock allows only one eBay browser
at a time across the two containers. Successful searches (including empty
results) are cached for five minutes; failures are not cached. Automatic browser
verification gets time to redirect to listings before being reported as a failure.
The worker stops its current pass when access is refused, instead of repeating
the failure for every watched product. It runs once at startup and every 10 hours.
Playwright and its Docker browser image are pinned together at 1.64.0. Container
dependencies live in `/opt/venv`, outside the mounted source directory, so the
two services cannot race while recreating a shared Python environment.

An HTTP 403 or a verification page that never finishes can still be an eBay access
restriction on the server's outbound traffic. A successful local test does not
prove an EC2 address will be accepted. The browser setup cannot guarantee access
from every network, and does not solve interactive CAPTCHAs.

For local development with a desktop display, run
`uv run --python 3.12 streamlit run main.py`. On a Linux server without a desktop,
use `xvfb-run -a uv run --python 3.12 streamlit run main.py --server.headless=true`.

Start both production services (no profile flag is needed):

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Run the offline regression tests in the frontend container with:

```bash
docker exec ebay_frontend xvfb-run -a uv run --python 3.12 python -m unittest discover -s tests -v
```

Run a separate live UI check (this sends real searches to eBay and fails if access
is blocked). Its default two searches check the first request and a cache hit:

```bash
docker exec ebay_frontend uv run --frozen --python 3.12 python scripts/validate_live_search.py
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
