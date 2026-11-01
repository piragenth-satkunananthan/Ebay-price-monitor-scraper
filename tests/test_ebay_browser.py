from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from ebay_browser import SearchError, open_ebay_page


class BrowserSessionTests(unittest.TestCase):
    def test_cookies_survive_browser_restart_and_errors_release_lock(self):
        with TemporaryDirectory() as directory:
            with patch("ebay_browser.PROFILE_DIR", Path(directory)):
                with open_ebay_page() as page:
                    page.context.add_cookies([{
                        "name": "session-test", "value": "public-session",
                        "domain": "www.ebay.com", "path": "/", "expires": 2_000_000_000,
                    }])
                with self.assertRaisesRegex(ValueError, "simulated failure"):
                    with open_ebay_page() as page:
                        self.assertTrue(any(cookie["name"] == "session-test"
                                            for cookie in page.context.cookies()))
                        raise ValueError("simulated failure")
                with open_ebay_page():
                    pass
                with open_ebay_page("worker") as page:
                    self.assertFalse(any(cookie["name"] == "session-test"
                                         for cookie in page.context.cookies()))
                with open_ebay_page() as page:
                    self.assertTrue(any(cookie["name"] == "session-test"
                                        for cookie in page.context.cookies()))

    def test_overlapping_browser_request_fails_with_bounded_wait(self):
        fake = Mock()
        fake.chromium.launch_persistent_context.return_value.pages = []
        manager = Mock()
        manager.__enter__ = Mock(return_value=fake)
        manager.__exit__ = Mock(return_value=False)
        with TemporaryDirectory() as directory:
            with patch("ebay_browser.PROFILE_DIR", Path(directory)):
                with patch("ebay_browser.sync_playwright", return_value=manager):
                    with open_ebay_page():
                        with patch("ebay_browser.LOCK_TIMEOUT_SECONDS", 0):
                            with self.assertRaisesRegex(SearchError, "Another eBay request"):
                                with open_ebay_page():
                                    self.fail("An overlapping browser was allowed")
        fake.chromium.launch_persistent_context.assert_called_once()

    def test_failed_browser_start_releases_lock(self):
        fake = Mock()
        fake.chromium.launch_persistent_context.side_effect = RuntimeError("launch failed")
        manager = Mock()
        manager.__enter__ = Mock(return_value=fake)
        manager.__exit__ = Mock(return_value=False)
        with TemporaryDirectory() as directory:
            with patch("ebay_browser.PROFILE_DIR", Path(directory)):
                with patch("ebay_browser.sync_playwright", return_value=manager):
                    for _ in range(2):
                        with self.assertRaisesRegex(RuntimeError, "launch failed"):
                            with open_ebay_page():
                                self.fail("Browser launch should fail")


if __name__ == "__main__":
    unittest.main()
