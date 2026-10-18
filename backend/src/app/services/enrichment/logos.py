"""Logo proposals from the site, then Facebook or Instagram when a key is set."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Callable
from urllib.parse import urlencode, urljoin, urlparse

from app.services.aws_proxy import AwsProxyError, http_invoke
from app.services.enrichment.constants import COPYRIGHT_NOTICE

_HANDLE_RE = re.compile(r"^[\w.\-]{2,80}$")
_GRAPH = "https://graph.facebook.com/v21.0"
Fetch = Callable[[str, dict[str, str]], dict[str, Any] | None]


def media_proposals(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One logo, then the other images as photos.

    A JSON-LD logo wins, then an icon link, then an image whose src, alt,
    or class says logo. The Open Graph image is the logo only when nothing
    else on the site is.
    """
    ranked: list[tuple[int, int, str, str]] = []
    for index, page in enumerate(pages):
        logo = _page_logo(page)
        if logo is not None:
            rank, src, alt = logo
            ranked.append((rank, index, src, alt))
    chosen = min(ranked, default=None)
    chosen_src = chosen[2] if chosen else ""
    proposals: list[dict[str, Any]] = []
    if chosen is not None:
        page = pages[chosen[1]]
        proposals.append(
            _media(
                page,
                chosen_src,
                "logo",
                "Logo",
                alt=chosen[3],
                logo=True,
            )
        )
    photo = 0
    seen = {chosen_src}
    for page in pages:
        for image in page.get("images") or []:
            if not isinstance(image, dict):
                continue
            src = _absolute(page, str(image.get("src") or ""))
            if not src or src in seen:
                continue
            seen.add(src)
            photo += 1
            proposals.append(
                _media(
                    page,
                    src,
                    "media",
                    f"Photo {photo}",
                    alt=str(image.get("alt") or ""),
                    logo=False,
                )
            )
    return proposals


def social_logo_proposals(
    org: Any,
    items: list[dict[str, Any]],
    *,
    fetch: Fetch | None = None,
) -> list[dict[str, Any]]:
    """Facebook and Instagram pictures. No key, or a failed call, adds nothing."""
    token = os.environ.get("META_GRAPH_API_KEY", "").strip()
    if not token:
        return []
    caller = fetch or _graph_fetch
    existing = {
        str((item.get("proposed") or {}).get("source_url") or "")
        for item in items
        if item.get("kind") == "add_media"
    }
    found: list[dict[str, Any]] = []
    specs = (
        (
            "facebook",
            "https://www.facebook.com/{handle}",
            f"{_GRAPH}/oembed_page",
            "Logo · Facebook",
        ),
        (
            "instagram",
            "https://www.instagram.com/{handle}/",
            f"{_GRAPH}/instagram_oembed",
            "Logo · Instagram",
        ),
    )
    for field, profile, endpoint, label in specs:
        handle = _handle(_social_value(org, items, field))
        if not handle:
            continue
        page_url = profile.format(handle=handle)
        url = f"{endpoint}?{urlencode({'url': page_url})}"
        thumbnail = _thumbnail(caller(url, {"Authorization": f"Bearer {token}"}))
        if not thumbnail or thumbnail in existing:
            continue
        existing.add(thumbnail)
        found.append(
            {
                "section": "Media",
                "kind": "add_media",
                "field": "logo",
                "label": label,
                "current": None,
                "proposed": {
                    "source_url": thumbnail,
                    "alt": label,
                    "logo": True,
                    "copyright_notice": COPYRIGHT_NOTICE,
                },
                "confidence": 0.8,
                "unverified": False,
                "evidence": [{"url": page_url, "quote": thumbnail[:180]}],
            }
        )
    return found


def _page_logo(page: dict[str, Any]) -> tuple[int, str, str] | None:
    logo = _jsonld_logo(page)
    if logo:
        src = _absolute(page, logo)
        if src:
            return 0, src, "Logo"
    for icon in page.get("icons") or []:
        if isinstance(icon, dict):
            src = _absolute(page, str(icon.get("href") or ""))
            if src:
                return 1, src, "Logo"
    for image in page.get("images") or []:
        if not isinstance(image, dict):
            continue
        alt = str(image.get("alt") or "")
        if alt.casefold() in {"og:image", "twitter:image"}:
            continue
        blob = " ".join(
            (str(image.get("src") or ""), alt, str(image.get("class") or ""))
        ).casefold()
        if "logo" in blob:
            src = _absolute(page, str(image.get("src") or ""))
            if src:
                return 2, src, alt or "Logo"
    for image in page.get("images") or []:
        if not isinstance(image, dict):
            continue
        if str(image.get("alt") or "").casefold() in {"og:image", "twitter:image"}:
            src = _absolute(page, str(image.get("src") or ""))
            if src:
                return 3, src, "Logo"
    return None


def _jsonld_logo(page: dict[str, Any]) -> str:
    for block in page.get("jsonld") or []:
        for node in _nodes(block):
            if not isinstance(node, dict):
                continue
            logo = node.get("logo")
            if isinstance(logo, str) and logo.strip():
                return logo.strip()
            if isinstance(logo, dict):
                url = logo.get("url") or logo.get("contentUrl")
                if isinstance(url, str) and url.strip():
                    return url.strip()
    return ""


def _nodes(block: object) -> list[object]:
    if isinstance(block, list):
        return block
    if isinstance(block, dict) and isinstance(block.get("@graph"), list):
        return list(block["@graph"])
    if isinstance(block, dict):
        return [block]
    return []


def _absolute(page: dict[str, Any], src: str) -> str:
    base = str(page.get("final_url") or page.get("url") or "")
    absolute = urljoin(base, src.strip())
    if not absolute.startswith(("http://", "https://")):
        return ""
    return absolute[:500]


def _media(
    page: dict[str, Any],
    src: str,
    field: str,
    label: str,
    *,
    alt: str,
    logo: bool,
) -> dict[str, Any]:
    url = str(page.get("final_url") or page.get("url") or "")
    return {
        "section": "Media",
        "kind": "add_media",
        "field": field,
        "label": label,
        "current": None,
        "proposed": {
            "source_url": src,
            "alt": alt[:200],
            "logo": logo,
            "copyright_notice": COPYRIGHT_NOTICE,
        },
        "confidence": 0.9,
        "unverified": False,
        "evidence": [{"url": url, "quote": src[:180]}],
    }


def _social_value(org: Any, items: list[dict[str, Any]], field: str) -> str:
    for item in items:
        if item.get("kind") != "update_organization" or item.get("field") != field:
            continue
        proposed = item.get("proposed") or {}
        if isinstance(proposed, dict) and proposed.get(field):
            return str(proposed[field])
    return str(getattr(org, field, "") or "")


def _handle(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    if text.startswith("@"):
        token = text[1:]
    else:
        parsed = urlparse(text if "://" in text else "")
        if parsed.hostname:
            parts = [part for part in parsed.path.split("/") if part]
            token = parts[-1] if parts else ""
        else:
            token = text
    token = token.split("?")[0].strip().strip("/")
    if not _HANDLE_RE.fullmatch(token):
        return ""
    return token


def _graph_fetch(url: str, headers: dict[str, str]) -> dict[str, Any] | None:
    try:
        result = http_invoke("GET", url, headers=headers, timeout=10)
    except (AwsProxyError, RuntimeError):
        return None
    if int(result.get("status") or 0) != 200:
        return None
    return result


def _thumbnail(result: dict[str, Any] | None) -> str:
    if not result:
        return ""
    try:
        payload = json.loads(result.get("body") or "")
    except json.JSONDecodeError:
        return ""
    if not isinstance(payload, dict):
        return ""
    thumbnail = payload.get("thumbnail_url")
    if isinstance(thumbnail, str) and thumbnail.startswith("https://"):
        return thumbnail[:500]
    return ""
