"""Logo proposals from the site, then Facebook or Instagram when a key is set."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Callable
from urllib.parse import quote, urlencode, urljoin, urlparse

from app.services.aws_proxy import AwsProxyError, http_invoke
from app.services.enrichment.constants import COPYRIGHT_NOTICE

_FB_HANDLE = re.compile(r"^[A-Za-z0-9.\-]{2,80}$")
_IG_HANDLE = re.compile(r"^[A-Za-z0-9._]{1,30}$")
_GRAPH = "https://graph.facebook.com/v21.0"
_GRAPH_TIMEOUT_SECONDS = 3
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
    deadline: float | None = None,
) -> list[dict[str, Any]]:
    """Facebook and Instagram pictures. No key, or a failed call, adds nothing.

    Page oEmbed no longer returns a thumbnail. Facebook uses the picture
    edge. Instagram uses Business Discovery, which needs the app's own
    professional account id.
    """
    token = os.environ.get("META_GRAPH_API_KEY", "").strip()
    if not token:
        return []
    caller = fetch or (
        lambda url, headers: _graph_fetch(url, headers, timeout=_http_timeout(deadline))
    )
    existing = {
        str((item.get("proposed") or {}).get("source_url") or "")
        for item in items
        if item.get("kind") == "add_media"
    }
    found: list[dict[str, Any]] = []
    specs = (
        ("facebook", "Logo · Facebook"),
        ("instagram", "Logo · Instagram"),
    )
    for field, label in specs:
        if not _has_time(deadline):
            break
        handle = _handle(_social_value(org, items, field))
        built = _social_request(field, handle)
        if built is None:
            continue
        url, page_url = built
        picture = _picture(caller(url, {"Authorization": f"Bearer {token}"}), field)
        if not picture or picture in existing:
            continue
        existing.add(picture)
        found.append(
            {
                "section": "Media",
                "kind": "add_media",
                "field": "logo",
                "label": label,
                "current": None,
                "proposed": {
                    "source_url": picture,
                    "alt": label,
                    "logo": True,
                    "copyright_notice": COPYRIGHT_NOTICE,
                },
                "confidence": 0.8,
                "unverified": False,
                "evidence": [{"url": page_url, "quote": picture[:180]}],
            }
        )
    return found


def _social_request(field: str, handle: str) -> tuple[str, str] | None:
    if field == "facebook":
        if not _FB_HANDLE.fullmatch(handle):
            return None
        query = urlencode({"redirect": "0", "type": "large"})
        url = f"{_GRAPH}/{quote(handle, safe='.-')}/picture?{query}"
        return url, f"https://www.facebook.com/{handle}"
    user_id = os.environ.get("META_INSTAGRAM_USER_ID", "").strip()
    if not user_id or not _IG_HANDLE.fullmatch(handle):
        return None
    if not re.fullmatch(r"[0-9]{2,40}", user_id):
        return None
    fields = f"business_discovery.username({handle}){{profile_picture_url}}"
    url = f"{_GRAPH}/{quote(user_id, safe='')}/?{urlencode({'fields': fields})}"
    return url, f"https://www.instagram.com/{handle}/"


def _page_logo(page: dict[str, Any]) -> tuple[int, str, str] | None:
    """JSON-LD, then a logo image, then a touch icon, then a favicon, then Open Graph."""
    best: tuple[int, str, str] | None = None

    def consider(rank: int, src: str, alt: str) -> None:
        nonlocal best
        if src and (best is None or rank < best[0]):
            best = (rank, src, alt)

    logo = _jsonld_logo(page)
    if logo:
        consider(0, _absolute(page, logo), "Logo")
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
            consider(1, _absolute(page, str(image.get("src") or "")), alt or "Logo")
    for icon in page.get("icons") or []:
        if not isinstance(icon, dict):
            continue
        rel = str(icon.get("rel") or "").casefold()
        rank = 2 if "apple-touch" in rel or "logo" in rel else 3
        consider(rank, _absolute(page, str(icon.get("href") or "")), "Logo")
    for image in page.get("images") or []:
        if not isinstance(image, dict):
            continue
        if str(image.get("alt") or "").casefold() in {"og:image", "twitter:image"}:
            consider(4, _absolute(page, str(image.get("src") or "")), "Logo")
    return best


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
    return token.split("?")[0].strip().strip("/")


def _has_time(deadline: float | None, needed: float = 1.0) -> bool:
    if deadline is None:
        return True
    return deadline - time.monotonic() > needed


def _http_timeout(deadline: float | None) -> int:
    if deadline is None:
        return _GRAPH_TIMEOUT_SECONDS
    remaining = int(deadline - time.monotonic())
    return max(1, min(_GRAPH_TIMEOUT_SECONDS, remaining))


def _graph_fetch(
    url: str, headers: dict[str, str], timeout: int = _GRAPH_TIMEOUT_SECONDS
) -> dict[str, Any] | None:
    try:
        result = http_invoke("GET", url, headers=headers, timeout=timeout)
    except (AwsProxyError, RuntimeError):
        return None
    if int(result.get("status") or 0) != 200:
        return None
    return result


def _picture(result: dict[str, Any] | None, field: str) -> str:
    if not result:
        return ""
    try:
        payload = json.loads(result.get("body") or "")
    except json.JSONDecodeError:
        return ""
    if not isinstance(payload, dict):
        return ""
    if field == "facebook":
        data = payload.get("data")
        if not isinstance(data, dict) or data.get("is_silhouette") is True:
            return ""
        url = data.get("url")
    else:
        data = payload.get("business_discovery")
        url = data.get("profile_picture_url") if isinstance(data, dict) else None
    if isinstance(url, str) and url.startswith("https://"):
        return url[:500]
    return ""
