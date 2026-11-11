from __future__ import annotations

import pytest

from price_monitor.models import ParseError
from price_monitor.sources.books import BooksAdapter

from tests.helpers import read_fixture


def test_parses_first_page() -> None:
    page = BooksAdapter().parse_page(
        read_fixture("books-page-1.html"),
        "https://books.toscrape.com/catalogue/page-1.html",
    )

    assert len(page.items) == 20
    assert page.total_pages == 50
    assert page.next_url == "https://books.toscrape.com/catalogue/page-2.html"
    assert page.warnings == []

    first = page.items[0]
    assert first.title == "A Light in the Attic"
    assert first.price == 51.77
    assert first.currency == "GBP"
    assert first.rating == 3
    assert first.in_stock is True
    assert first.stock_text == "In stock"
    assert first.url == (
        "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"
    )
    assert first.external_id.startswith("/catalogue/a-light-in-the-attic_1000/")
    assert first.image_url and first.image_url.endswith(".jpg")


def test_parses_middle_page_and_keeps_rating_values() -> None:
    page = BooksAdapter().parse_page(
        read_fixture("books-page-2.html"),
        "https://books.toscrape.com/catalogue/page-2.html",
    )
    assert len(page.items) == 20
    assert page.next_url == "https://books.toscrape.com/catalogue/page-3.html"
    assert {item.rating for item in page.items} <= {1, 2, 3, 4, 5}
    assert all(item.currency == "GBP" for item in page.items)
    assert all(item.external_id.startswith("/catalogue/") for item in page.items)


def test_last_page_has_no_next_link() -> None:
    page = BooksAdapter().parse_page(
        read_fixture("books-page-50.html"),
        "https://books.toscrape.com/catalogue/page-50.html",
    )
    assert len(page.items) == 20
    assert page.next_url is None
    assert page.total_pages == 50


def test_broken_product_is_skipped_with_warning() -> None:
    html = """
    <html><body>
      <article class="product_pod">
        <h3><a href="broken/index.html" title="No price book">No price book</a></h3>
        <div class="product_price"><p class="price_color">not a price</p></div>
        <p class="instock availability">In stock</p>
      </article>
      <article class="product_pod">
        <h3><a href="good/index.html" title="Good book">Good book</a></h3>
        <div class="product_price"><p class="price_color">£12.34</p></div>
        <p class="instock availability">In stock</p>
      </article>
    </body></html>
    """
    page = BooksAdapter().parse_page(html, "https://books.toscrape.com/catalogue/page-1.html")
    assert [item.title for item in page.items] == ["Good book"]
    assert len(page.warnings) == 1
    assert "not a price" in page.warnings[0].message


def test_out_of_stock_is_captured() -> None:
    html = """
    <article class="product_pod">
      <h3><a href="x/index.html" title="Sold out">Sold out</a></h3>
      <p class="star-rating Five"></p>
      <div class="product_price"><p class="price_color">£9.99</p></div>
      <p class="instock availability">Out of stock</p>
    </article>
    """
    page = BooksAdapter().parse_page(html, "https://books.toscrape.com/catalogue/page-1.html")
    assert page.items[0].in_stock is False
    assert page.items[0].rating == 5
    assert page.next_url is None


def test_empty_page_raises() -> None:
    with pytest.raises(ParseError):
        BooksAdapter().parse_page(
            "<html><body><p>maintenance</p></body></html>",
            "https://books.toscrape.com/catalogue/page-1.html",
        )
