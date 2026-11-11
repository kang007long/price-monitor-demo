"""Adapter for https://quotes.toscrape.com.

This site has no prices. It exists in the demo as a second, *optional* adapter
to show that the crawler is source-agnostic and that parser tests do not need
network access. The dashboard reads the books dataset only.
"""

from __future__ import annotations

import hashlib
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from price_monitor.models import PageResult, ParsedItem, ParseError, ParseWarning
from price_monitor.sources.base import SourceSpec
from price_monitor.sources.util import collapse_whitespace


class QuotesAdapter:
    spec = SourceSpec(
        key="quotes",
        name="Quotes to Scrape",
        base_url="https://quotes.toscrape.com/",
        start_url="https://quotes.toscrape.com/page/1/",
        robots_url="https://quotes.toscrape.com/robots.txt",
        license_note=(
            "Quotes to Scrape is a public sandbox built for scraping practice. "
            "Quotes are attributed to their authors on the page."
        ),
        default_max_pages=10,
        currency="",
    )

    def fallback_next_url(self, page_url: str, page_number: int) -> str | None:
        match = re.search(r"/page/(\d+)/", page_url)
        if match is None:
            return None
        return (
            page_url[: match.start()]
            + f"/page/{int(match.group(1)) + 1}/"
            + page_url[match.end() :]
        )

    def parse_page(self, html: str, page_url: str) -> PageResult:
        soup = BeautifulSoup(html, "html.parser")
        quote_nodes = soup.select("div.quote")
        if not quote_nodes:
            raise ParseError(
                f"no quotes found on {page_url}; the page layout may have changed"
            )

        items: list[ParsedItem] = []
        warnings: list[ParseWarning] = []
        for node in quote_nodes:
            text_node = node.select_one("span.text")
            author_node = node.select_one("small.author")
            if text_node is None or author_node is None:
                warnings.append(
                    ParseWarning(page_url, "quote without text or author; skipped")
                )
                continue
            text = collapse_whitespace(text_node.get_text())
            author = collapse_whitespace(author_node.get_text())
            if not text or not author:
                warnings.append(
                    ParseWarning(page_url, "quote with empty text or author; skipped")
                )
                continue

            tags = [
                collapse_whitespace(tag.get_text())
                for tag in node.select("div.tags a.tag")
                if collapse_whitespace(tag.get_text())
            ]
            author_link = node.select_one("a[href^='/author/']")
            url = (
                urljoin(page_url, author_link["href"])
                if author_link is not None
                else page_url
            )
            digest = hashlib.sha256(f"{text}\n{author}".encode("utf-8")).hexdigest()
            items.append(
                ParsedItem(
                    external_id=f"quote:{digest[:20]}",
                    title=text,
                    url=url,
                    price=None,
                    currency=None,
                    in_stock=True,
                    stock_text="n/a",
                    category=", ".join(tags) or None,
                )
            )

        next_url = None
        next_link = soup.select_one("ul.pager li.next a[href]")
        if next_link is not None:
            next_url = urljoin(page_url, next_link["href"])

        return PageResult(
            items=items,
            next_url=next_url,
            warnings=warnings,
            total_pages=None,
        )
