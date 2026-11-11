from __future__ import annotations

import httpx
import pytest

from price_monitor.http import FetchError, PoliteClient, RobotsDenied


class Harness:
    def __init__(self, handler, **kwargs):
        self.requests: list[httpx.Request] = []
        self.sleeps: list[float] = []
        self.now = 0.0

        def wrapped(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            return handler(request)

        def sleep(seconds: float) -> None:
            self.sleeps.append(seconds)
            self.now += seconds

        def clock() -> float:
            return self.now

        defaults = {
            "transport": httpx.MockTransport(wrapped),
            "sleep": sleep,
            "clock": clock,
            "min_interval": 1.0,
            "max_retries": 2,
        }
        defaults.update(kwargs)
        self.client = PoliteClient(**defaults)

    def close(self) -> None:
        self.client.close()


def page_response(request: httpx.Request, text: str = "ok") -> httpx.Response:
    return httpx.Response(200, text=text, request=request)


def test_sends_descriptive_user_agent_and_fetches_robots_once() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404, request=request)
        return page_response(request)

    harness = Harness(handler, user_agent="TestBot/9.9 (demo)")
    try:
        harness.client.get("https://books.toscrape.com/catalogue/page-1.html")
        harness.client.get("https://books.toscrape.com/catalogue/page-2.html")
    finally:
        harness.close()

    robots_requests = [r for r in harness.requests if r.url.path == "/robots.txt"]
    assert len(robots_requests) == 1
    assert all(r.headers["user-agent"] == "TestBot/9.9 (demo)" for r in harness.requests)
    assert all(r.url.host == "books.toscrape.com" for r in harness.requests)


def test_robots_404_allows_pages() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404, request=request)
        return page_response(request, "hello")

    harness = Harness(handler)
    try:
        response = harness.client.get("https://books.toscrape.com/catalogue/page-1.html")
        assert response.text == "hello"
    finally:
        harness.close()


def test_robots_disallow_blocks_without_fetching_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                text="User-agent: *\nDisallow: /catalogue\n",
                request=request,
            )
        return page_response(request)

    harness = Harness(handler)
    try:
        with pytest.raises(RobotsDenied):
            harness.client.get("https://books.toscrape.com/catalogue/page-1.html")
    finally:
        harness.close()
    assert [r.url.path for r in harness.requests] == ["/robots.txt"]


def test_robots_allows_unlisted_paths() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                text="User-agent: *\nDisallow: /private\n",
                request=request,
            )
        return page_response(request, "allowed")

    harness = Harness(handler)
    try:
        assert harness.client.get("https://quotes.toscrape.com/page/1/").text == "allowed"
    finally:
        harness.close()


def test_robots_5xx_denies_access() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request)

    harness = Harness(handler, max_retries=0)
    try:
        with pytest.raises(RobotsDenied):
            harness.client.get("https://books.toscrape.com/catalogue/page-1.html")
    finally:
        harness.close()


def test_retries_server_errors_then_succeeds() -> None:
    calls = {"page": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404, request=request)
        calls["page"] += 1
        if calls["page"] == 1:
            return httpx.Response(503, request=request)
        return page_response(request, "recovered")

    harness = Harness(handler)
    try:
        response = harness.client.get("https://books.toscrape.com/catalogue/page-1.html")
    finally:
        harness.close()
    assert response.text == "recovered"
    assert calls["page"] == 2
    assert 1.0 in harness.sleeps


def test_retry_after_is_honoured() -> None:
    calls = {"page": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404, request=request)
        calls["page"] += 1
        if calls["page"] == 1:
            return httpx.Response(
                429, headers={"Retry-After": "2"}, request=request
            )
        return page_response(request)

    harness = Harness(handler)
    try:
        harness.client.get("https://books.toscrape.com/catalogue/page-1.html")
    finally:
        harness.close()
    assert 2.0 in harness.sleeps


def test_timeout_is_retried() -> None:
    calls = {"page": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404, request=request)
        calls["page"] += 1
        if calls["page"] == 1:
            raise httpx.ReadTimeout("slow", request=request)
        return page_response(request)

    harness = Harness(handler)
    try:
        assert harness.client.get("https://books.toscrape.com/catalogue/page-1.html")
    finally:
        harness.close()
    assert calls["page"] == 2


def test_404_is_not_retried() -> None:
    calls = {"page": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404, request=request)
        calls["page"] += 1
        return httpx.Response(404, request=request)

    harness = Harness(handler)
    try:
        with pytest.raises(FetchError) as excinfo:
            harness.client.get("https://books.toscrape.com/catalogue/page-1.html")
    finally:
        harness.close()
    assert excinfo.value.status_code == 404
    assert calls["page"] == 1


def test_throttles_between_requests() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return page_response(request)

    harness = Harness(handler, min_interval=1.0)
    try:
        harness.client.get("https://books.toscrape.com/page-1", check_robots=False)
        harness.client.get("https://books.toscrape.com/page-2", check_robots=False)
        harness.client.get("https://books.toscrape.com/page-3", check_robots=False)
    finally:
        harness.close()
    assert harness.sleeps == [1.0, 1.0]
    assert harness.now == 2.0


def test_refuses_non_practice_hosts() -> None:
    harness = Harness(lambda request: page_response(request))
    try:
        with pytest.raises(FetchError, match="non-practice host"):
            harness.client.get("https://example.com/")
    finally:
        harness.close()
    assert harness.requests == []


def test_retry_exhaustion_raises_fetch_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404, request=request)
        return httpx.Response(502, request=request)

    harness = Harness(handler, max_retries=1)
    try:
        with pytest.raises(FetchError) as excinfo:
            harness.client.get("https://books.toscrape.com/catalogue/page-1.html")
    finally:
        harness.close()
    assert excinfo.value.status_code == 502
    assert len([r for r in harness.requests if r.url.path != "/robots.txt"]) == 2


def test_redirect_off_the_allowlist_is_never_sent() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404, request=request)
        return httpx.Response(
            302,
            headers={"Location": "https://example.com/private"},
            request=request,
        )

    harness = Harness(handler)
    try:
        with pytest.raises(FetchError, match="non-practice host"):
            harness.client.get("https://books.toscrape.com/catalogue/page-1.html")
    finally:
        harness.close()
    assert harness.requests
    assert all(request.url.host == "books.toscrape.com" for request in harness.requests)


def test_redirect_within_the_allowlist_is_followed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404, request=request)
        if request.url.path == "/catalogue/page-1.html":
            return httpx.Response(
                302,
                headers={"Location": "/catalogue/page-2.html"},
                request=request,
            )
        return page_response(request, "page two")

    harness = Harness(handler)
    try:
        response = harness.client.get("https://books.toscrape.com/catalogue/page-1.html")
        assert response.text == "page two"
    finally:
        harness.close()


def test_source_specific_robots_url_is_used() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/custom-robots.txt":
            return httpx.Response(
                200,
                text="User-agent: *\nDisallow: /catalogue\n",
                request=request,
            )
        if request.url.path == "/robots.txt":
            raise AssertionError("the default robots.txt must not be requested")
        raise AssertionError("page must not be requested when robots disallows it")

    harness = Harness(handler)
    try:
        harness.client.register_robots(
            "https://books.toscrape.com/custom-robots.txt"
        )
        with pytest.raises(RobotsDenied):
            harness.client.get("https://books.toscrape.com/catalogue/page-1.html")
    finally:
        harness.close()
    assert [request.url.path for request in harness.requests] == [
        "/custom-robots.txt"
    ]


def test_redirect_hops_are_rate_limited() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/catalogue/page-1.html":
            return httpx.Response(
                302,
                headers={"Location": "/catalogue/page-2.html"},
                request=request,
            )
        return page_response(request, "page two")

    harness = Harness(handler, min_interval=1.0)
    try:
        response = harness.client.get(
            "https://books.toscrape.com/catalogue/page-1.html",
            check_robots=False,
        )
        assert response.text == "page two"
    finally:
        harness.close()
    assert harness.sleeps == [1.0]
    assert [request.url.path for request in harness.requests] == [
        "/catalogue/page-1.html",
        "/catalogue/page-2.html",
    ]
