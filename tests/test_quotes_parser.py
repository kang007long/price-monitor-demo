from __future__ import annotations

import pytest

from price_monitor.models import ParseError
from price_monitor.sources.quotes import QuotesAdapter

from tests.helpers import read_fixture


def test_parses_quotes_page() -> None:
    page = QuotesAdapter().parse_page(
        read_fixture("quotes-page-1.html"), "https://quotes.toscrape.com/page/1/"
    )
    assert len(page.items) == 10
    assert page.next_url == "https://quotes.toscrape.com/page/2/"
    assert page.warnings == []

    first = page.items[0]
    assert first.title.startswith("“The world as we have created it")
    assert first.price is None
    assert first.currency is None
    assert "thinking" in (first.category or "")
    assert first.url == "https://quotes.toscrape.com/author/Albert-Einstein"
    assert first.external_id.startswith("quote:")


def test_quote_ids_are_unique_and_stable() -> None:
    html = read_fixture("quotes-page-1.html")
    first = QuotesAdapter().parse_page(html, "https://quotes.toscrape.com/page/1/")
    second = QuotesAdapter().parse_page(html, "https://quotes.toscrape.com/page/1/")
    ids = [item.external_id for item in first.items]
    assert len(ids) == len(set(ids))
    assert ids == [item.external_id for item in second.items]


def test_empty_quotes_page_raises() -> None:
    with pytest.raises(ParseError):
        QuotesAdapter().parse_page(
            "<html><body>nothing here</body></html>",
            "https://quotes.toscrape.com/page/1/",
        )
