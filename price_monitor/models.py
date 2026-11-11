"""Small, dependency-free value objects shared by adapters and the pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ParsedItem:
    """One thing found on a listing page.

    ``external_id`` is the stable de-duplication key for a source. For books it
    is the product path; for quotes it is a hash of the quote text and author.
    """

    external_id: str
    title: str
    url: str
    price: float | None = None
    currency: str | None = None
    in_stock: bool = True
    stock_text: str = ""
    rating: int | None = None
    category: str | None = None
    image_url: str | None = None


@dataclass(frozen=True, slots=True)
class ParseWarning:
    page_url: str
    message: str


@dataclass(frozen=True, slots=True)
class PageResult:
    items: list[ParsedItem]
    next_url: str | None
    warnings: list[ParseWarning] = field(default_factory=list)
    total_pages: int | None = None


class ParseError(ValueError):
    """Raised when a page no longer matches the expected structure."""


@dataclass(frozen=True, slots=True)
class ObservationOutcome:
    item_id: int
    is_new: bool
    price_changed: bool
    stock_changed: bool
    previous_price: float | None
    previous_in_stock: bool | None
