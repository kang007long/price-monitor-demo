"""Adapter for https://books.toscrape.com (a public scraping sandbox)."""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from price_monitor.models import PageResult, ParsedItem, ParseError, ParseWarning
from price_monitor.sources.base import SourceSpec
from price_monitor.sources.util import (
    PriceParseError,
    collapse_whitespace,
    parse_availability,
    parse_price,
    parse_rating,
)

_TOTAL_PAGES_RE = re.compile(r"Page\s+\d+\s+of\s+(\d+)")


class BooksAdapter:
    spec = SourceSpec(
        key="books",
        name="Books to Scrape",
        base_url="https://books.toscrape.com/",
        start_url="https://books.toscrape.com/catalogue/page-1.html",
        robots_url="https://books.toscrape.com/robots.txt",
        license_note=(
            "Books to Scrape is a public sandbox built for scraping practice. "
            "It is not a real shop and contains no real customer data."
        ),
        default_max_pages=50,
        currency="GBP",
    )

    def fallback_next_url(self, page_url: str, page_number: int) -> str | None:
        match = re.search(r"page-(\d+)\.html", page_url)
        if match is None:
            return None
        return (
            page_url[: match.start()]
            + f"page-{int(match.group(1)) + 1}.html"
            + page_url[match.end() :]
        )

    def parse_page(self, html: str, page_url: str) -> PageResult:
        soup = BeautifulSoup(html, "html.parser")
        articles = soup.find_all("article", class_="product_pod")
        if not articles:
            raise ParseError(
                f"no product cards found on {page_url}; the page layout may have changed"
            )

        items: list[ParsedItem] = []
        warnings: list[ParseWarning] = []
        for article in articles:
            link = article.select_one("h3 a")
            price_node = article.select_one(".price_color")
            if link is None or not link.get("href"):
                warnings.append(
                    ParseWarning(page_url, "product card without a title link; skipped")
                )
                continue

            title = (
                link.get("title") or collapse_whitespace(link.get_text())
            ).strip()
            if not title:
                warnings.append(
                    ParseWarning(page_url, "product card without a title; skipped")
                )
                continue

            product_url = urljoin(page_url, link["href"])
            image = article.select_one(".image_container img")
            image_url = (
                urljoin(page_url, image["src"])
                if image is not None and image.get("src")
                else None
            )

            try:
                if price_node is None:
                    raise PriceParseError("missing .price_color node")
                price, currency = parse_price(price_node.get_text())
            except PriceParseError as exc:
                warnings.append(
                    ParseWarning(page_url, f"{title!r}: {exc}; skipped")
                )
                continue

            availability = article.select_one("p.availability")
            in_stock, stock_text = parse_availability(
                availability.get_text() if availability is not None else ""
            )
            rating_node = article.select_one(".star-rating")
            rating = parse_rating(
                rating_node.get("class", []) if rating_node is not None else []
            )

            items.append(
                ParsedItem(
                    external_id=urlparse(product_url).path,
                    title=title,
                    url=product_url,
                    price=price,
                    currency=currency,
                    in_stock=in_stock,
                    stock_text=stock_text,
                    rating=rating,
                    image_url=image_url,
                )
            )

        next_url = None
        next_link = soup.select_one("ul.pager li.next a[href]")
        if next_link is not None:
            next_url = urljoin(page_url, next_link["href"])

        total_pages = None
        current = soup.select_one("ul.pager li.current")
        if current is not None:
            match = _TOTAL_PAGES_RE.search(collapse_whitespace(current.get_text()))
            if match:
                total_pages = int(match.group(1))

        return PageResult(
            items=items,
            next_url=next_url,
            warnings=warnings,
            total_pages=total_pages,
        )
