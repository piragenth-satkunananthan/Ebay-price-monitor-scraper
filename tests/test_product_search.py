"""Regression tests use routed browser pages; no requests are sent to eBay."""

import ast
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright

from product_search import SearchError, parse_search_results, scrape_search_page


def card(item_id="123456789012", title="Pencil", layout="s-card"):
    return f'''<div class="{layout}">
        <a href="/itm/{item_id}?tracking=1"><img src="pencil.jpg"></a>
        <div class="{layout}__title">{title}</div>
        <span class="{layout}__price">$10.00</span>
    </div>'''


class ParserTests(unittest.TestCase):
    def test_keeps_first_and_last_real_listings(self):
        html = "".join(card(str(123456789010 + i)) for i in range(5))
        self.assertEqual(len(parse_search_results(html)), 5)

    def test_older_cards_and_missing_images(self):
        html = card(layout="s-item").replace('<img src="pencil.jpg">', "")
        self.assertEqual(parse_search_results(html), [{
            "title": "Pencil", "link": "https://www.ebay.com/itm/123456789012",
            "price_range": "$10.00", "image_link": "",
        }])

    def test_nested_cards_deduplicate_and_keep_price_range(self):
        html = '<div class="su-card-container">' + card() + '</div>' + card()
        html = html.replace("$10.00", "$10.00 to $15.00")
        results = parse_search_results(html)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["price_range"], "$10.00 to $15.00")

    def test_skips_placeholders_malformed_and_external_links(self):
        html = card(title="Shop on eBay")
        html += card().replace("/itm/123456789012?tracking=1", "https://example.com/itm/123456789012")
        html += card().replace("/itm/123456789012?tracking=1", "http://[bad")
        html += card().replace('<span class="s-card__price">$10.00</span>', "")
        html += card("123456789013", "Real listing")
        self.assertEqual([r["title"] for r in parse_search_results(html)], ["Real listing"])

    def test_lazy_image_and_slugged_listing_link(self):
        html = card().replace('src="pencil.jpg"', 'src="placeholder.gif" data-src="real.jpg"')
        html = html.replace("/itm/123456789012", "/itm/Pencil-set/123456789012")
        result = parse_search_results(html)[0]
        self.assertEqual(result["image_link"], "real.jpg")
        self.assertEqual(result["link"], "https://www.ebay.com/itm/123456789012")

    def test_prefers_primary_title_over_accessibility_text(self):
        html = card(title='<span class="primary">Pencil</span><span>Opens in a new window</span>')
        self.assertEqual(parse_search_results(html)[0]["title"], "Pencil")


class BrowserSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=False)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.page = self.browser.new_page()
        self.addCleanup(self.page.close)

    def serve(self, body, status=200):
        self.page.route("**/*", lambda route: route.fulfill(
            status=status, content_type="text/html", body=body))

    def test_results_without_footer_and_encoded_keyword(self):
        self.serve(card())
        results = scrape_search_page("pen & pencil #1", self.page)
        self.assertEqual(len(results), 1)
        self.assertEqual(parse_qs(urlsplit(self.page.url).query), {"_nkw": ["pen & pencil #1"]})

    def test_waits_for_delayed_listing_content(self):
        self.serve('''<div id="results"></div><script>
            setTimeout(() => document.querySelector('#results').innerHTML =
            `%s`, 150);
        </script>''' % card())
        self.assertEqual(len(scrape_search_page("pencil", self.page)), 1)

    def test_http_errors_do_not_wait_for_selectors(self):
        for status in (403, 429, 500):
            with self.subTest(status=status):
                self.page.unroute("**/*")
                self.serve("<title>Error Page | eBay</title>SORRY", status=status)
                with patch.object(self.page, "wait_for_function") as wait:
                    with self.assertRaisesRegex(SearchError, str(status)):
                        scrape_search_page("pencil", self.page)
                    wait.assert_not_called()

    def test_verification_page_with_success_status(self):
        self.serve("<title>Pardon Our Interruption</title>Please verify yourself")
        with patch("product_search.SEARCH_TIMEOUT_MS", 150):
            with self.assertRaisesRegex(SearchError, "verification"):
                scrape_search_page("pencil", self.page)

    def test_automatic_verification_redirects_to_real_results(self):
        self.page.route("**/*", lambda route: route.fulfill(
            content_type="text/html",
            body=(card() if 'verified=1' in route.request.url else '''
                <title>Pardon Our Interruption...</title>Checking your browser
                <script>setTimeout(() => location.href = '/sch/i.html?verified=1', 200)</script>
            ''')))
        self.assertEqual(len(scrape_search_page("pencil", self.page)), 1)

    def test_automatic_verification_replaces_content_without_navigation(self):
        self.serve('''<title>Pardon Our Interruption...</title><body>Checking your browser
            <script>setTimeout(() => {
                document.title = 'Search results'; document.body.innerHTML = `%s`;
            }, 200)</script></body>''' % card())
        self.assertEqual(len(scrape_search_page("pencil", self.page)), 1)

    def test_hundred_results_does_not_mean_zero_results(self):
        self.serve("<h1>100 results for pencil</h1><p>Unrecognized card layout</p>")
        with patch("product_search.SEARCH_TIMEOUT_MS", 150):
            with self.assertRaisesRegex(SearchError, "in time"):
                scrape_search_page("pencil", self.page)

    def test_genuine_empty_results(self):
        self.serve("<h1>0 results for this keyword</h1>")
        self.assertEqual(scrape_search_page("pencil", self.page), [])

    def test_unknown_layout_is_an_error_instead_of_empty_results(self):
        self.serve("<h1>An unfamiliar page</h1>")
        with patch("product_search.SEARCH_TIMEOUT_MS", 100):
            with self.assertRaisesRegex(SearchError, "in time"):
                scrape_search_page("pencil", self.page)

    def test_navigation_timeout_is_a_search_error(self):
        with patch.object(self.page, "goto", side_effect=PlaywrightTimeoutError("timeout")):
            with self.assertRaisesRegex(SearchError, "in time"):
                scrape_search_page("pencil", self.page)

    def test_blank_keyword_does_not_navigate(self):
        self.assertEqual(scrape_search_page("  ", self.page), [])
        self.assertEqual(self.page.url, "about:blank")


class SearchUITests(unittest.TestCase):
    def test_blocked_search_shows_message_and_clears_old_results(self):
        import pandas as pd
        from streamlit.testing.v1 import AppTest

        # Exercise the real page function without importing main.py's database/navigation.
        source = (Path(__file__).resolve().parents[1] / "main.py").read_text()
        function = next(node for node in ast.parse(source).body
                        if isinstance(node, ast.FunctionDef) and node.name == "product_search_page")
        preamble = '''import streamlit as st
import pandas as pd
import logging
from playwright.sync_api import Error as PlaywrightError
from product_search import SearchError, search_ebay as fetch_search_results
logger = logging.getLogger(__name__)
'''
        app = AppTest.from_string(preamble + ast.get_source_segment(source, function) + "\nproduct_search_page()")
        app.run()
        app.session_state.results_df = pd.DataFrame([{"title": "Old search result"}])
        app.text_input[0].set_value("pencil")
        message = "eBay refused this search (HTTP 403). Please try again later or use CSV import."
        with patch("product_search.search_ebay", side_effect=SearchError(message)):
            app.button[0].click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.error[0].value, message)
        self.assertTrue(app.session_state.results_df.empty)


if __name__ == "__main__":
    unittest.main()
