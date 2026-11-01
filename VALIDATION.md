# eBay access validation — 2026-11-01

Local search is restored. The fixes are deployed on EC2, but direct eBay access
from EC2 remains refused. Production search is **not** validated as working.

| Check | Observed result |
| --- | --- |
| Local offline regression suite, updated image | 27 tests passed |
| EC2 offline regression suite, final candidate | 27 tests passed in 36.95 seconds |
| Local UI: `pencil`, fresh session | 69 listings in 7.31 seconds |
| Local UI: `pencil`, second fresh session | 69 cached listings in 0.21 seconds |
| Local UI: `mechanical pencil`, fresh session | 64 listings in 3.56 seconds |
| Local UI after worker access failure: `notebook` | 60 listings in 4.31 seconds |
| Public EC2 UI: `pencil`, after deployment | HTTP 403 reported in 11.25 seconds; no UI exception; live check failed |
| Production frontend health | HTTP 200 |
| Production services | Frontend and worker running; zero restarts; no OOM kill |
| Production Python/browser package | Playwright 1.64.0 loaded from `/opt/venv` |

The previous implementation rejected the title “Pardon Our Interruption” as soon
as it appeared. A diagnostic browser showed that this temporary page could
redirect to listings normally after several seconds. The scraper now waits for
that redirect, with a bounded timeout. Tests cover both successful redirects and
verification pages that never finish.

The old image used Chromium 145. The package and image now match at Playwright
1.64.0 / Chromium 156. Search and worker profiles are persistent, isolated by role
and package version, and excluded from Git and image builds. A file lock prevents
overlapping eBay browser processes across the two services. Successful searches
are cached for five minutes; failures are not cached.

The worker no longer scrapes during import and then immediately scrapes again.
It uses headed Chromium under Xvfb and stops its pass after an access refusal,
without adding false price entries or repeating the refusal for the watchlist.
It retains the existing 10-hour interval.

Production originally retained Compose labels referencing the directory's old
name. The first promotion attempt encountered a container-name conflict and
restored the source/image. The successful promotion reused the existing
`ebay-price-monitor-scraper` project. That name is now explicit in the production
Compose file. Before changing the mount path, the deployment verified that the
running container and `/home/ubuntu/ebay` referenced the same SQLite inode.
Database files were excluded from the source archive and deployment backup.

Successful production rollback artifacts, on EC2:

- Source: `/tmp/ebay-before-browser-fix-20261101-054432.tar.gz`
- Image: `ebay-price-monitor:rollback-20261101-054432`
- Deployed source archive SHA-256: `492eaf03f3c78d08d11b66ec7b0a0609972d3fab072c88141f1b710e6ce26126`

Direct EC2 diagnostics received HTTP 403 with `Server: AkamaiGHost`, including
from the eBay homepage. A verification redirect also ended at an eBay error page.
The current-browser candidate and the updated public UI both reproduced the
refusal. This establishes that eBay is refusing those outbound requests; it does
not reveal eBay's internal rule or prove a particular IP-reputation diagnosis.
The user chose to keep direct EC2 access and report any remaining block. No proxy,
remote browser gateway, API switch, or CAPTCHA-solving mechanism was configured.

Repeatable commands are in README.md. `scripts/validate_live_search.py` uses a
fresh Streamlit session for each search and exits unsuccessfully if listings are
not returned; existing results cannot make a later blocked search pass.
