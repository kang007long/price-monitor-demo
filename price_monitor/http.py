"""Polite HTTP client: robots.txt, 1 req/s throttle, bounded retries.

Design notes
------------
* One ``PoliteClient`` is shared by the whole batch so the rate limit is global,
  not per page.
* ``robots.txt`` is fetched once per origin and cached. RFC 9309 treats a 404 as
  "no robots.txt" (allow all) and a 5xx as "temporarily unavailable" (disallow).
  Both practice sites currently return 404, which is why the demo can run.
* Redirects are followed manually so every hop passes through the same
  throttle, allowlist, and retry logic. 4xx responses are surfaced immediately;
  the pipeline records them and continues with other pages where possible.
"""

from __future__ import annotations

import time
import urllib.robotparser
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx

from price_monitor import config


class FetchError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, url: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.url = url


class RobotsDenied(FetchError):
    pass


@dataclass(slots=True)
class _RobotsRules:
    parser: urllib.robotparser.RobotFileParser | None
    allow_all: bool

    def allowed(self, user_agent: str, url: str) -> bool:
        if self.allow_all:
            return True
        if self.parser is None:
            return False
        return self.parser.can_fetch(user_agent, url)


class PoliteClient:
    def __init__(
        self,
        *,
        user_agent: str = config.USER_AGENT,
        min_interval: float = config.MIN_REQUEST_INTERVAL,
        timeout: float = config.REQUEST_TIMEOUT,
        max_retries: int = config.MAX_RETRIES,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.user_agent = user_agent
        self.min_interval = max(0.0, min_interval)
        self.max_retries = max(0, max_retries)
        self._sleep = sleep
        self._clock = clock
        self._last_request_at: float | None = None
        self._robots: dict[str, _RobotsRules] = {}
        self._robots_urls: dict[str, str] = {}
        self._client = httpx.Client(
            headers={
                "User-Agent": user_agent,
                "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            },
            follow_redirects=False,
            timeout=httpx.Timeout(timeout),
            transport=transport,
            # Every request, including each redirect hop, passes this hook.
            event_hooks={"request": [self._guard_request]},
        )

    def __enter__(self) -> "PoliteClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def register_robots(self, robots_url: str) -> None:
        """Use a source-specific robots.txt URL for its origin."""

        parsed = urlparse(robots_url)
        if not self._host_allowed(robots_url):
            raise ValueError(f"robots URL is outside the allowlist: {robots_url}")
        self._robots_urls[f"{parsed.scheme}://{parsed.netloc}"] = robots_url

    # -- public API ---------------------------------------------------------

    def get(self, url: str, *, check_robots: bool = True) -> httpx.Response:
        if not self._host_allowed(url):
            host = urlparse(url).hostname
            raise FetchError(
                f"refusing to fetch non-practice host {host!r}", url=url
            )
        if check_robots and not self._robots_rules(url).allowed(self.user_agent, url):
            raise RobotsDenied(
                f"robots.txt disallows {url}", url=url
            )
        return self._request_with_retries(url, check_robots=check_robots)

    # -- internals ----------------------------------------------------------

    def _host_allowed(self, url: str) -> bool:
        return (urlparse(url).hostname or "").lower() in config.ALLOWED_HOSTS

    def _guard_request(self, request: httpx.Request) -> None:
        """Reject off-allowlist redirects before they are sent."""

        url = str(request.url)
        parsed = urlparse(url)
        if not self._host_allowed(url):
            raise FetchError(
                f"refusing redirect/request to non-practice host {parsed.hostname!r}",
                url=url,
            )
        origin = f"{parsed.scheme}://{parsed.netloc}"
        cached = self._robots.get(origin)
        if cached is not None and not cached.allowed(self.user_agent, url):
            raise FetchError(f"robots.txt disallows redirect target {url}", url=url)

    def _throttle(self) -> None:
        if self._last_request_at is not None and self.min_interval > 0:
            elapsed = self._clock() - self._last_request_at
            remaining = self.min_interval - elapsed
            if remaining > 0:
                self._sleep(remaining)
        self._last_request_at = self._clock()

    REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
    MAX_REDIRECTS = 5

    def _request_with_retries(
        self, url: str, *, check_robots: bool = True
    ) -> httpx.Response:
        current = url
        redirects = 0
        while True:
            response = self._request_once_with_retries(current)
            if response.status_code not in self.REDIRECT_STATUSES:
                return response

            location = response.headers.get("Location")
            if not location:
                raise FetchError(
                    f"HTTP {response.status_code} without a Location from {current}",
                    status_code=response.status_code,
                    url=current,
                )
            target = urljoin(str(response.url), location)
            if not self._host_allowed(target):
                raise FetchError(
                    f"refusing redirect to non-practice host {urlparse(target).hostname!r}",
                    url=target,
                )
            if check_robots and not self._robots_rules(target).allowed(
                self.user_agent, target
            ):
                raise RobotsDenied(f"robots.txt disallows {target}", url=target)

            redirects += 1
            if redirects > self.MAX_REDIRECTS:
                raise FetchError(f"too many redirects from {url}", url=current)
            current = target

    def _request_once_with_retries(self, url: str) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            self._throttle()
            try:
                response = self._client.get(url)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                self._sleep(self._backoff(attempt))
                continue

            if response.status_code in {429, 500, 502, 503, 504}:
                last_error = FetchError(
                    f"HTTP {response.status_code} from {url}",
                    status_code=response.status_code,
                    url=url,
                )
                if attempt >= self.max_retries:
                    break
                self._sleep(self._retry_delay(response, attempt))
                continue

            if response.status_code >= 400:
                raise FetchError(
                    f"HTTP {response.status_code} from {url}",
                    status_code=response.status_code,
                    url=url,
                )
            return response

        if isinstance(last_error, FetchError):
            raise last_error
        raise FetchError(
            f"request failed after {self.max_retries + 1} attempts: {last_error}",
            url=url,
        ) from last_error

    @staticmethod
    def _backoff(attempt: int) -> float:
        return float(min(30, 2**attempt))

    def _retry_delay(self, response: httpx.Response, attempt: int) -> float:
        header = response.headers.get("Retry-After")
        if header:
            try:
                return max(0.0, min(30.0, float(header.strip())))
            except ValueError:
                pass
        return self._backoff(attempt)

    def _robots_rules(self, url: str) -> _RobotsRules:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin in self._robots:
            return self._robots[origin]

        robots_url = self._robots_urls.get(origin, f"{origin}/robots.txt")
        try:
            response = self._request_with_retries(
                robots_url, check_robots=False
            )
        except FetchError as exc:
            if exc.status_code in {404, 410}:
                rules = _RobotsRules(None, True)
            else:
                rules = _RobotsRules(None, False)
            self._robots[origin] = rules
            return rules

        if response.status_code in {401, 403}:
            rules = _RobotsRules(None, False)
        else:
            parser = urllib.robotparser.RobotFileParser()
            parser.set_url(robots_url)
            parser.parse(response.text.splitlines())
            rules = _RobotsRules(parser, False)
        self._robots[origin] = rules
        return rules
