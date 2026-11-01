"""Fetch eBay search listings and distinguish unavailable pages from empty searches."""

import logging
import re
from urllib.parse import urlencode, urljoin, urlsplit

from bs4 import BeautifulSoup
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


logger = logging.getLogger(__name__)
SEARCH_TIMEOUT_MS = 20_000
CARD_SELECTOR = ".su-card-container, .s-card, .s-item"
BLOCKED_TITLES = (
    "error page", "access denied", "pardon our interruption", "security check",
    "security measure", "robot check",
)
BLOCKED_MESSAGES = (
    "something went wrong on our end", "verify you're human", "verify you are human",
    "checking your browser", "please verify yourself",
)
EMPTY_MESSAGES = ("0 results for", "no results found", "no exact matches found")


class SearchError(RuntimeError):
    """An eBay search could not be completed; safe to display in the UI."""


def parse_search_results(html):
    """Read current and older card layouts without relying on card positions."""
    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen = set()
    for card in soup.select(CARD_SELECTOR):
        title_node = card.select_one(".s-card__title .primary") or card.select_one(
            ".s-card__title, .s-item__title"
        )
        price_nodes = card.select(".s-card__price, .s-item__price")
        if not title_node or not price_nodes:
            continue
        title = title_node.get_text(" ", strip=True)
        price = " ".join(node.get_text(" ", strip=True) for node in price_nodes).strip()
        if not title or not price or title.lower() == "shop on ebay":
            continue
        for anchor in card.select("a[href]"):
            try:
                url = urlsplit(urljoin("https://www.ebay.com", anchor["href"]))
            except ValueError:
                continue
            item = re.search(r"/itm/(?:[^/?#]+/)?(\d{9,15})(?:/|$)", url.path)
            if (url.scheme in ("http", "https")
                    and (url.hostname == "ebay.com" or (url.hostname or "").endswith(".ebay.com"))
                    and item):
                link = f"https://www.ebay.com/itm/{item.group(1)}"
                break
        else:
            continue
        if link in seen:
            continue
        image = card.select_one("img.s-card__image, img.s-item__image-img, img")
        image_link = (image.get("data-src") or image.get("src") or "") if image else ""
        results.append({"title": title, "link": link, "price_range": price, "image_link": image_link})
        seen.add(link)
    return results


def scrape_search_page(keyword, page):
    keyword = keyword.strip()
    if not keyword:
        return []
    url = "https://www.ebay.com/sch/i.html?" + urlencode({"_nkw": keyword})
    try:
        response = page.goto(url, wait_until="domcontentloaded", timeout=SEARCH_TIMEOUT_MS)
        if response is None:
            raise SearchError("eBay did not return a search page. Please try again later.")
        if response.status >= 400:
            logger.warning("eBay search failed: HTTP %s, URL %s", response.status, page.url)
            if response.status in (403, 429):
                raise SearchError(
                    f"eBay refused this search (HTTP {response.status}). "
                    "Please try again later or use CSV import."
                )
            raise SearchError(f"eBay search is unavailable (HTTP {response.status}). Please try again later.")

        # Wait for useful content or a known empty/error state, never an unrelated footer.
        page.wait_for_function(
            """({cards, blockedTitles, blockedMessages, emptyMessages}) => {
                const title = document.title.toLowerCase();
                const text = (document.body?.innerText || '').toLowerCase();
                return [...document.querySelectorAll(cards)].some(card =>
                    card.querySelector('a[href*="/itm/"]') &&
                    card.querySelector('.s-card__title, .s-item__title')?.textContent.trim() &&
                    card.querySelector('.s-card__price, .s-item__price')?.textContent.trim()) ||
                    blockedTitles.some(value => title.includes(value)) ||
                    blockedMessages.some(value => text.includes(value)) ||
                    emptyMessages.some(value => text.includes(value)) ||
                    !!document.querySelector('#captcha_form, iframe[src*="captcha"], .srp-save-null-search');
            }""",
            arg={"cards": CARD_SELECTOR, "blockedTitles": BLOCKED_TITLES,
                 "blockedMessages": BLOCKED_MESSAGES, "emptyMessages": EMPTY_MESSAGES},
            timeout=SEARCH_TIMEOUT_MS,
        )
        soup = BeautifulSoup(page.content(), "html.parser")
        title = soup.title.get_text(" ", strip=True).lower() if soup.title else ""
        text = soup.get_text(" ", strip=True).lower()
        if (any(value in title for value in BLOCKED_TITLES)
                or any(value in text for value in BLOCKED_MESSAGES)
                or soup.select_one('#captcha_form, iframe[src*="captcha"]')):
            raise SearchError(
                "eBay returned an error or verification page. Please try again later or use CSV import."
            )
        results = parse_search_results(str(soup))
        if results:
            return results
        if any(value in text for value in EMPTY_MESSAGES) or soup.select_one(".srp-save-null-search"):
            return []
        raise SearchError("eBay's search page could not be read. Please try again later or use CSV import.")
    except PlaywrightTimeoutError as exc:
        raise SearchError(
            "eBay did not load a readable search page in time. Please try again later or use CSV import."
        ) from exc
