"""Fetch a provider website: robots, pacing, same-site, and a page cap."""

from __future__ import annotations

import http.client
import socket
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

from app.services.enrichment.constants import (
    CRAWL_TIME_BUDGET_SECONDS,
    USER_AGENT,
)
from app.services.enrichment.guard import (
    CrawlError,
    check_fetch_url,
    is_social_host,
    public_address,
    same_site,
)
from app.services.enrichment.parse import link_score, parse_html

_ALLOWED_TYPES = (
    "text/html",
    "application/xhtml+xml",
    "text/plain",
    "application/ld+json",
)


@dataclass
class FetchResult:
    status: int
    url: str
    content_type: str
    body: bytes
    location: str
    truncated: bool = False


FetchOne = Callable[[str, int], FetchResult]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Surface the 3xx so the caller can check the next host first."""

    def http_error_302(self, req, fp, code, msg, headers):  # noqa: ANN001
        raise urllib.error.HTTPError(req.full_url, code, msg, headers, fp)

    http_error_301 = http_error_303 = http_error_307 = http_error_308 = http_error_302


class _PinnedHTTPS(urllib.request.HTTPSHandler):
    """Connect to a checked IP and verify the certificate for the hostname."""

    def __init__(self, server_hostname: str):
        self._ssl_context = ssl.create_default_context()
        super().__init__(context=self._ssl_context)
        self._server_hostname = server_hostname

    def https_open(self, req: urllib.request.Request):  # noqa: ANN201
        return self.do_open(
            http.client.HTTPSConnection,
            req,
            context=self._ssl_context,
            server_hostname=self._server_hostname,
        )


def fetch_public(
    url: str,
    max_bytes: int,
    timeout: int = 8,
    *,
    deadline: float | None = None,
) -> FetchResult:
    """GET one URL. Redirects are returned, not followed.

    The TCP connection uses the IP checked by public_address, so a DNS
    change between the check and the connect cannot reach a private address.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise CrawlError("refusing non-http URL")
    if parsed.username or parsed.password:
        raise CrawlError("refusing URL with credentials")
    ip = public_address(parsed.hostname)
    pinned, host_header, server_name = _pinned_target(url, ip)
    request = urllib.request.Request(
        pinned,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        },
        method="GET",
    )
    request.add_unredirected_header("Host", host_header)
    handlers: list[urllib.request.BaseHandler] = [_NoRedirect()]
    if parsed.scheme == "https":
        handlers.append(_PinnedHTTPS(server_name))
    opener = urllib.request.build_opener(*handlers)
    budget = _remaining(deadline, timeout)
    if budget <= 0:
        raise TimeoutError("crawl budget exceeded")
    try:
        with opener.open(request, timeout=budget) as response:  # noqa: S310
            body, truncated = _read_bounded(response, max_bytes, deadline, timeout)
            status = int(getattr(response, "status", None) or response.getcode() or 200)
            final = url
            ctype = str(response.headers.get("Content-Type") or "")
            location = str(response.headers.get("Location") or "")
    except urllib.error.HTTPError as exc:
        body, truncated = _read_bounded(exc, max_bytes, deadline, timeout)
        status = int(exc.code)
        final = url
        ctype = str(exc.headers.get("Content-Type") or "") if exc.headers else ""
        location = str(exc.headers.get("Location") or "") if exc.headers else ""
    except socket.timeout as exc:
        raise TimeoutError("crawl budget exceeded") from exc
    return FetchResult(
        status=status,
        url=final,
        content_type=ctype,
        body=body,
        location=location,
        truncated=truncated,
    )


def _pinned_target(url: str, ip: str) -> tuple[str, str, str]:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    port = parsed.port
    ip_host = f"[{ip}]" if ":" in ip else ip
    netloc = f"{ip_host}:{port}" if port else ip_host
    pinned = urlunparse(
        (parsed.scheme, netloc, parsed.path or "/", "", parsed.query, "")
    )
    host_header = host if port is None else f"{host}:{port}"
    return pinned, host_header, host


def _remaining(deadline: float | None, timeout: float) -> float:
    if deadline is None:
        return float(timeout)
    return min(float(timeout), deadline - time.monotonic())


def _read_bounded(
    response: object,
    max_bytes: int,
    deadline: float | None,
    timeout: float,
) -> tuple[bytes, bool]:
    chunks: list[bytes] = []
    total = 0
    limit = max_bytes + 1
    reader = getattr(response, "read", None)
    if reader is None:
        return b"", False
    while total < limit:
        budget = _remaining(deadline, timeout)
        if budget <= 0:
            raise TimeoutError("crawl budget exceeded")
        _set_socket_timeout(response, budget)
        try:
            block = reader(min(65536, limit - total))
        except socket.timeout as exc:
            raise TimeoutError("crawl budget exceeded") from exc
        if not block:
            break
        chunks.append(block)
        total += len(block)
    body = b"".join(chunks)
    truncated = len(body) > max_bytes
    return body[:max_bytes], truncated


def _set_socket_timeout(response: object, seconds: float) -> None:
    raw = getattr(getattr(response, "fp", None), "raw", None)
    sock = getattr(raw, "_sock", None)
    if sock is not None and hasattr(sock, "settimeout"):
        sock.settimeout(seconds)


def _follow(
    url: str,
    *,
    fetch_one: FetchOne,
    max_bytes: int,
    hops: int = 3,
) -> FetchResult:
    current = url
    for _ in range(hops + 1):
        check_fetch_url(current)
        result = fetch_one(current, max_bytes)
        if result.status not in {301, 302, 303, 307, 308} or not result.location:
            return result
        current = urljoin(result.url or current, result.location)
    raise CrawlError("too many redirects")


def crawl_site(
    seed_url: str,
    *,
    max_pages: int = 6,
    max_page_bytes: int = 1_000_000,
    time_budget_seconds: int = CRAWL_TIME_BUDGET_SECONDS,
    fetch_one: FetchOne | None = None,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.monotonic,
) -> dict[str, object]:
    """Crawl the seed and a few same-site pages. Never raises for HTTP errors."""
    started = now()
    deadline = started + max(1, time_budget_seconds)

    def bounded(url: str, max_bytes: int) -> FetchResult:
        if now() >= deadline:
            raise TimeoutError("crawl budget exceeded")
        if fetch_one is not None:
            return fetch_one(url, max_bytes)
        return fetch_public(url, max_bytes, deadline=deadline)

    host = urlparse(seed_url).hostname or ""
    parsers: dict[str, RobotFileParser | None] = {}

    def robots_for(url: str) -> RobotFileParser | None:
        name = (urlparse(url).hostname or "").lower()
        if name not in parsers:
            parsers[name] = _robots(
                url,
                fetch_one=bounded,
                max_bytes=100_000,
                deadline=deadline,
                now=now,
            )
        return parsers[name]

    robots = robots_for(seed_url)
    if robots is not None and not _allowed(robots, seed_url):
        return _done("failed", "robots.txt disallows this bot", [])
    queue: list[tuple[int, str]] = [(1000, seed_url)]
    seen = {seed_url}
    pages: list[dict[str, object]] = []
    total_bytes = 0
    last_fetch = 0.0
    while queue and len(pages) < max_pages and now() < deadline:
        queue.sort(key=lambda item: item[0], reverse=True)
        _score, url = queue.pop(0)
        page_robots = robots_for(url)
        if page_robots is not None and not _allowed(page_robots, url):
            continue
        if last_fetch:
            wait = 1.0 - (now() - last_fetch)
            if wait > 0 and now() + wait < deadline:
                sleep(wait)
        try:
            result = _follow(url, fetch_one=bounded, max_bytes=max_page_bytes)
        except (CrawlError, urllib.error.URLError, TimeoutError, OSError):
            continue
        last_fetch = now()
        final_url = result.url or url
        final_host = urlparse(final_url).hostname or ""
        if not same_site(host, final_host):
            continue
        final_robots = robots_for(final_url)
        if final_robots is not None and not _allowed(final_robots, final_url):
            continue
        ctype = result.content_type.split(";", 1)[0].strip().lower()
        if ctype and not any(ctype.startswith(allowed) for allowed in _ALLOWED_TYPES):
            continue
        markup = result.body.decode("utf-8", errors="replace")
        total_bytes += len(result.body)
        if result.status >= 400:
            continue
        page = parse_html(final_url, markup)
        refresh = str(page.get("meta_refresh") or "")
        if refresh and not str(page.get("text") or "").strip() and refresh not in seen:
            seen.add(refresh)
            queue.append((900, refresh))
            continue
        page["final_url"] = final_url
        page["status"] = result.status
        pages.append(page)
        raw_links = page.get("links")
        for link in raw_links if isinstance(raw_links, list) else []:
            if not isinstance(link, dict):
                continue
            href = str(link.get("href") or "")
            link_host = urlparse(href).hostname or ""
            if (
                href in seen
                or not same_site(host, link_host)
                or is_social_host(link_host)
            ):
                continue
            seen.add(href)
            queue.append((link_score(href, str(link.get("text") or "")), href))
    if not pages:
        return _done("failed", "website returned no readable page", [])
    seed_text = str(pages[0].get("text") or "")
    if len(seed_text) < 200 and len(pages) == 1:
        return _done(
            "render_required",
            "This site needs a browser before it can be read.",
            pages,
            total_bytes,
        )
    return _done("ok", "", pages, total_bytes)


def _robots(
    seed_url: str,
    *,
    fetch_one: FetchOne,
    max_bytes: int,
    deadline: float,
    now: Callable[[], float],
) -> RobotFileParser | None:
    if now() >= deadline:
        return None
    parsed = urlparse(seed_url)
    robots_url = f"{parsed.scheme}://{parsed.hostname}/robots.txt"
    try:
        result = _follow(robots_url, fetch_one=fetch_one, max_bytes=max_bytes)
    except (CrawlError, urllib.error.URLError, TimeoutError, OSError):
        return None
    if result.status >= 400:
        return None
    parser = RobotFileParser()
    parser.parse(result.body.decode("utf-8", errors="replace").splitlines())
    return parser


def _allowed(parser: RobotFileParser, url: str) -> bool:
    try:
        return bool(parser.can_fetch(USER_AGENT, url))
    except Exception:
        return True


def _done(
    status: str,
    error: str,
    pages: list[dict[str, object]],
    total_bytes: int = 0,
) -> dict[str, object]:
    return {
        "status": status,
        "error": error,
        "pages": pages,
        "pages_fetched": len(pages),
        "bytes_fetched": total_bytes,
    }
