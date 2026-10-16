"""SSRF and same-site checks for a website enrichment crawl."""

from __future__ import annotations

import ipaddress
import socket
from typing import Callable
from urllib.parse import urlparse

from app.services.enrichment.constants import MULTI_PART_SUFFIXES, SOCIAL_HOSTS

CGNAT_V4 = ipaddress.ip_network("100.64.0.0/10")
Resolve = Callable[..., list]


class CrawlError(ValueError):
    """The URL is not safe to fetch."""


def _hostname(host: str) -> str:
    return (host or "").split("%")[0].strip().lower().rstrip(".")


def registrable_domain(host: str) -> str:
    """eTLD+1. Multi-part suffixes come from the vendored list."""
    labels = [part for part in _hostname(host).split(".") if part]
    if len(labels) < 2:
        return ""
    last_two = ".".join(labels[-2:])
    last_three = ".".join(labels[-3:])
    if last_two in MULTI_PART_SUFFIXES and len(labels) >= 3:
        return ".".join(labels[-3:])
    if last_three in MULTI_PART_SUFFIXES and len(labels) >= 4:
        return ".".join(labels[-4:])
    return last_two


def same_site(left: str, right: str) -> bool:
    """True when both hosts share a registrable domain."""
    a = registrable_domain(left)
    b = registrable_domain(right)
    return bool(a) and a == b


def social_field(host: str) -> str | None:
    """Organization column for a social host, or None when it is only skipped."""
    domain = registrable_domain(host)
    if domain in SOCIAL_HOSTS:
        return SOCIAL_HOSTS[domain]
    return None


def is_social_host(host: str) -> bool:
    return registrable_domain(host) in SOCIAL_HOSTS


def host_is_blocked(host: str, *, resolve: Resolve = socket.getaddrinfo) -> bool:
    """True for loopback, private, link-local, and names that do not resolve."""
    hostname = _hostname(host)
    if not hostname or hostname in {"localhost", "localhost.localdomain"}:
        return True
    if hostname.endswith(".local") or hostname.endswith(".internal"):
        return True
    try:
        ipaddress.ip_address(hostname)
        literal = True
    except ValueError:
        literal = False
    if literal:
        return _ip_blocked(hostname)
    try:
        infos = resolve(hostname, None)
    except socket.gaierror:
        return True
    if not infos:
        return True
    for info in infos:
        if _ip_blocked(info[4][0]):
            return True
    return False


def _ip_blocked(raw: str) -> bool:
    try:
        ip = ipaddress.ip_address(raw)
    except ValueError:
        return True
    if (
        ip.is_loopback
        or ip.is_link_local
        or ip.is_private
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or (ip.version == 4 and ip in CGNAT_V4)
    ):
        return True
    return False


def validate_seed_url(url: str) -> str:
    """Return a normalised http(s) URL, or raise CrawlError."""
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise CrawlError("website must be an http or https URL")
    if parsed.username or parsed.password:
        raise CrawlError("website must not include credentials")
    host = _hostname(parsed.hostname)
    try:
        ipaddress.ip_address(host)
        raise CrawlError("website must use a hostname, not an IP address")
    except ValueError:
        pass
    if host_is_blocked(host):
        raise CrawlError("website host is not allowed")
    if is_social_host(host):
        raise CrawlError("website must be the provider site, not a social page")
    path = parsed.path or "/"
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{parsed.scheme}://{host}{path}{query}"


def public_address(host: str, *, resolve: Resolve = socket.getaddrinfo) -> str:
    """Return one public IP for this host. The caller connects to that IP."""
    hostname = _hostname(host)
    if not hostname or hostname in {"localhost", "localhost.localdomain"}:
        raise CrawlError("refusing private or disallowed host")
    if hostname.endswith(".local") or hostname.endswith(".internal"):
        raise CrawlError("refusing private or disallowed host")
    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        literal = None
    if literal is not None:
        if _ip_blocked(str(literal)):
            raise CrawlError("refusing private or disallowed host")
        return str(literal)
    try:
        infos = resolve(hostname, None)
    except socket.gaierror as exc:
        raise CrawlError("refusing private or disallowed host") from exc
    if not infos:
        raise CrawlError("refusing private or disallowed host")
    chosen: str | None = None
    for info in infos:
        address = str(info[4][0])
        if _ip_blocked(address):
            raise CrawlError("refusing private or disallowed host")
        if chosen is None:
            chosen = address
    if chosen is None:
        raise CrawlError("refusing private or disallowed host")
    return chosen


def check_fetch_url(url: str, *, resolve: Resolve = socket.getaddrinfo) -> None:
    """Refuse a crawl target that is not public http(s)."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise CrawlError("refusing non-http URL")
    if parsed.username or parsed.password:
        raise CrawlError("refusing URL with credentials")
    if host_is_blocked(parsed.hostname, resolve=resolve):
        raise CrawlError("refusing private or disallowed host")
