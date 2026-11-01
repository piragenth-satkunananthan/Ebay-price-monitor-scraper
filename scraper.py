"""Update saved prices without retrying an entire watchlist after an access block."""

import logging
import re

from playwright.sync_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError

import database as db
from ebay_browser import SearchError, open_ebay_page


logger = logging.getLogger(__name__)


def main():
    products = db.retrive_product_link_from_db()
    if products.empty:
        logger.info("No monitored products; no browser needed")
        return True
    updated = 0
    with open_ebay_page("worker") as page:
        for _, row in products.iterrows():
            product_id = int(row["id"])
            try:
                _, price = scrape_product(str(row["url"]), page)
                db.add_price_history_to_db(product_id, price)
                updated += 1
            except SearchError as exc:
                logger.warning("Stopping price update after eBay access failure: %s", exc)
                return False
            except (PlaywrightError, ValueError) as exc:
                logger.warning("Could not update product %s: %s", product_id, exc)
    logger.info("Updated %s of %s monitored products", updated, len(products))
    return True


def scrape_product(url, page):
    response = page.goto(url, wait_until="domcontentloaded", timeout=30_000)
    if response is None:
        raise SearchError("eBay did not return a product page.")
    if response.status in (403, 429) or response.status >= 500:
        raise SearchError(f"eBay refused product access (HTTP {response.status}).")
    if response.status >= 400:
        raise ValueError(f"Product page returned HTTP {response.status}")
    try:
        page.wait_for_function("""() => {
            const text = (document.body?.innerText || '').toLowerCase();
            return document.querySelector('div.x-price-primary, span.x-price-approx__price') ||
                document.title.toLowerCase().includes('error page') ||
                document.title.toLowerCase().includes('access denied') ||
                text.includes('something went wrong on our end');
        }""", timeout=20_000)
    except PlaywrightTimeoutError as exc:
        if ("splashui" in page.url or "pardon our interruption" in page.title().lower()
                or page.locator('#captcha_form, iframe[src*="captcha"]').count()):
            raise SearchError("eBay product access requires browser verification.") from exc
        raise
    if any(value in page.title().lower() for value in ("error page", "access denied")):
        raise SearchError("eBay returned an error page for product access.")
    name = page.locator("div.x-item-title, h1.x-item-title__mainTitle").first.inner_text(timeout=2000)
    price_node = page.query_selector("span.x-price-approx__price")
    if price_node:
        price_text = price_node.inner_text().split("$")[-1]
    else:
        price_text = page.locator("div.x-price-primary").first.inner_text(timeout=2000).split("$")[-1]
    price = float(re.sub(r"[^0-9.]", "", price_text))
    return name, price


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
