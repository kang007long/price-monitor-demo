"""Site adapter registry. Import here so the CLI only knows source keys."""

from __future__ import annotations

from price_monitor.sources.base import SiteAdapter, SourceSpec
from price_monitor.sources.books import BooksAdapter
from price_monitor.sources.quotes import QuotesAdapter

ADAPTERS: dict[str, SiteAdapter] = {
    adapter.spec.key: adapter for adapter in (BooksAdapter(), QuotesAdapter())
}


def get_adapter(key: str) -> SiteAdapter:
    try:
        return ADAPTERS[key]
    except KeyError as exc:
        available = ", ".join(sorted(ADAPTERS))
        raise ValueError(f"unknown source {key!r}; choose one of: {available}") from exc


__all__ = ["ADAPTERS", "SiteAdapter", "SourceSpec", "get_adapter"]
