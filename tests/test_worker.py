import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd
from playwright.sync_api import sync_playwright

from ebay_browser import SearchError


def load_worker(database):
    path = Path(__file__).resolve().parents[1] / "scraper.py"
    spec = importlib.util.spec_from_file_location("worker_under_test", path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"database": database}):
        spec.loader.exec_module(module)
    return module


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.worker = load_worker(self.db)

    def test_import_does_not_scrape_or_query_database(self):
        self.db.retrive_product_link_from_db.assert_not_called()

    def test_empty_watchlist_does_not_launch_browser(self):
        self.db.retrive_product_link_from_db.return_value = pd.DataFrame()
        with patch.object(self.worker, "open_ebay_page") as browser:
            self.assertTrue(self.worker.main())
            browser.assert_not_called()

    def test_block_stops_watchlist_without_writing_false_prices(self):
        self.db.retrive_product_link_from_db.return_value = pd.DataFrame([
            {"id": 1, "url": "https://www.ebay.com/itm/123456789012"},
            {"id": 2, "url": "https://www.ebay.com/itm/123456789013"},
        ])
        with patch.object(self.worker, "open_ebay_page"):
            with patch.object(self.worker, "scrape_product", side_effect=SearchError("HTTP 403")) as scrape:
                self.assertFalse(self.worker.main())
        scrape.assert_called_once()
        self.db.add_price_history_to_db.assert_not_called()

    def test_successful_prices_are_written_to_the_correct_product(self):
        self.db.retrive_product_link_from_db.return_value = pd.DataFrame([
            {"id": 42, "url": "https://www.ebay.com/itm/123456789012"},
        ])
        with patch.object(self.worker, "open_ebay_page"):
            with patch.object(self.worker, "scrape_product", return_value=("Pencil", 9.99)):
                self.assertTrue(self.worker.main())
        self.db.add_price_history_to_db.assert_called_once_with(42, 9.99)


class ProductPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=False)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.worker = load_worker(MagicMock())
        self.page = self.browser.new_page()
        self.addCleanup(self.page.close)

    def test_product_verification_redirect_can_finish(self):
        self.page.route("**/*", lambda route: route.fulfill(content_type="text/html", body=(
            '<div class="x-item-title">Pencil</div><div class="x-price-primary">US $9.99</div>'
            if "verified=1" in route.request.url else '''<title>Pardon Our Interruption...</title>
            <script>setTimeout(() => location.href = '/itm/123456789012?verified=1', 150)</script>''')))
        self.assertEqual(self.worker.scrape_product("https://www.ebay.com/itm/123456789012", self.page),
                         ("Pencil", 9.99))

    def test_blocked_product_raises_access_error(self):
        self.page.route("**/*", lambda route: route.fulfill(status=403, body="Access denied"))
        with self.assertRaisesRegex(SearchError, "403"):
            self.worker.scrape_product("https://www.ebay.com/itm/123456789012", self.page)


if __name__ == "__main__":
    unittest.main()
