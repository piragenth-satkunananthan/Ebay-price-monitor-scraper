"""Persistent profiles with one bounded browser process at a time."""

from contextlib import contextmanager
import fcntl
from importlib.metadata import version
from pathlib import Path
import time

from playwright.sync_api import sync_playwright


PROFILE_DIR = Path(__file__).resolve().parent / ".browser-state"
LOCK_TIMEOUT_SECONDS = 10
BROWSER_TIMEOUT_MS = 30_000


class SearchError(RuntimeError):
    """An eBay access failure with a message suitable for the dashboard."""


@contextmanager
def open_ebay_page(role="search"):
    """Keep cookies between requests and prevent overlapping Chromium processes.

    flock works across the frontend and worker containers because both mount
    this directory. It is released by the OS if a process is interrupted.
    """
    if role not in ("search", "worker"):
        raise ValueError("Unknown browser role")
    try:
        # The outer directory must be traversable by Docker's build-context
        # validator even though .dockerignore excludes it. Cookie data stays
        # inside the private chromium directory.
        PROFILE_DIR.mkdir(mode=0o755, parents=True, exist_ok=True)
        # Separate price-worker cookies from search cookies, and do not carry
        # an older Chromium profile into a browser-version upgrade.
        browser_profile = PROFILE_DIR / f"{role}-{version('playwright')}"
        browser_profile.mkdir(mode=0o700, exist_ok=True)
        lock_file = (PROFILE_DIR / "browser.lock").open("a")
    except OSError as exc:
        raise SearchError("Browser session storage is unavailable. Please contact the site administrator.") from exc

    with lock_file:
        deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
        while True:
            try:
                fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise SearchError("Another eBay request is running. Please try again shortly.")
                time.sleep(0.1)
        try:
            with sync_playwright() as playwright:
                context = playwright.chromium.launch_persistent_context(
                    str(browser_profile),
                    headless=False,
                    locale="en-US",
                    viewport={"width": 1440, "height": 1000},
                    timeout=BROWSER_TIMEOUT_MS,
                )
                try:
                    page = context.pages[0] if context.pages else context.new_page()
                    page.set_default_timeout(BROWSER_TIMEOUT_MS)
                    page.set_default_navigation_timeout(BROWSER_TIMEOUT_MS)
                    yield page
                finally:
                    context.close()
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
