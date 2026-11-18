"""Configuration defaults for the price-monitor demo.

Everything that touches the network is deliberately conservative: one request
per second at most, a descriptive User-Agent, and bounded retries.
"""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parent

DEFAULT_DB_PATH = Path(
    os.environ.get("PRICE_MONITOR_DB", REPO_ROOT / "data" / "price_monitor.db")
)
DEFAULT_WEB_DIR = Path(os.environ.get("PRICE_MONITOR_WEB_DIR", REPO_ROOT / "web"))

# Replace the example URL with your own repository/contact before pointing this
# at anything outside the two practice sites. A clear UA is part of being polite.
USER_AGENT = os.environ.get(
    "PRICE_MONITOR_USER_AGENT",
    "PriceMonitorDemo/1.0 (+https://github.com/kang007long/price-monitor-demo; "
    "educational portfolio demo; polite crawler)",
)

# 1.1s spacing is slightly slower than the documented 1 req/s ceiling so timer
# jitter cannot push us over it.
# Never allow the configured default below the documented 1 request/second cap.
MIN_REQUEST_INTERVAL = max(
    1.0, float(os.environ.get("PRICE_MONITOR_MIN_INTERVAL", "1.1"))
)
REQUEST_TIMEOUT = float(os.environ.get("PRICE_MONITOR_TIMEOUT", "20"))
MAX_RETRIES = int(os.environ.get("PRICE_MONITOR_MAX_RETRIES", "3"))

# How many days of history the dashboard keeps per item (and the cap used when
# serialising the static data file).
MAX_HISTORY_DAYS = int(os.environ.get("PRICE_MONITOR_MAX_HISTORY_DAYS", "60"))

# Demo-only simulation bounds: synthetic prices stay within +/-20% of the real
# scraped price so the numbers remain plausible.
SIMULATION_MAX_DRIFT = 0.20
SIMULATION_DAILY_SIGMA = 0.018
SIMULATION_STOCK_PROBABILITY = 0.03

# The only sites this project is allowed to touch. See README ("Scope & ethics").
ALLOWED_HOSTS = frozenset({"books.toscrape.com", "quotes.toscrape.com"})
