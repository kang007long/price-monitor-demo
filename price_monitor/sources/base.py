"""Source adapter contract.

Adding a site means writing one adapter module: describe where it starts, how
many pages it has, and how to turn one HTML page into ``ParsedItem``s plus the
next URL. The crawler itself is source-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from price_monitor.models import PageResult


@dataclass(frozen=True, slots=True)
class SourceSpec:
    key: str
    name: str
    base_url: str
    start_url: str
    robots_url: str
    license_note: str
    default_max_pages: int
    currency: str = "GBP"


class SiteAdapter(Protocol):
    spec: SourceSpec

    def parse_page(self, html: str, page_url: str) -> PageResult:
        """Parse one listing page. Raise ``ParseError`` if the layout changed."""
        ...

    def fallback_next_url(self, page_url: str, page_number: int) -> str | None:
        """Best-effort next URL when the current page could not be read.

        Lets the crawler skip one bad page and continue the rest of the
        catalogue instead of abandoning every remaining page.
        """
        ...
