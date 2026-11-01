"""Opt-in live UI check; a blocked search is reported as a failure, never a pass."""

import argparse
import json
import time

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8501")
    parser.add_argument("--keyword", action="append", dest="keywords")
    args = parser.parse_args()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for keyword in args.keywords or ["pencil", "pencil"]:
                # A fresh Streamlit session cannot display the preceding search's
                # results while a new request is still running.
                page = browser.new_page()
                started = time.monotonic()
                try:
                    page.goto(args.base_url.rstrip("/") + "/product_search_page",
                              wait_until="domcontentloaded", timeout=30_000)
                    page.get_by_placeholder("e.g. RTX 4090, MacBook Pro M3…").fill(keyword)
                    started = time.monotonic()
                    page.get_by_role("button", name="🔍 Search eBay").click()
                    page.wait_for_function("""() => /\\d+ Results/.test(document.body.innerText) ||
                        document.querySelector('[data-testid="stAlert"], [data-testid="stException"]')
                    """, timeout=90_000)
                    result = {
                        "keyword": keyword,
                        "seconds": round(time.monotonic() - started, 2),
                        "headings": page.get_by_role("heading").all_inner_texts(),
                        "alerts": page.locator('[data-testid="stAlert"]').all_inner_texts(),
                        "exceptions": page.locator('[data-testid="stException"]').count(),
                    }
                    print(json.dumps(result), flush=True)
                    if result["alerts"] or result["exceptions"]:
                        return 1
                except Exception as exc:
                    print(json.dumps({"keyword": keyword, "error": str(exc),
                                      "seconds": round(time.monotonic() - started, 2)}), flush=True)
                    return 1
                finally:
                    page.close()
        finally:
            browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
