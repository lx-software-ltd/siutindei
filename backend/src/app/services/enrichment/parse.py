"""Turn one HTML page into text, links, images, and structured facts."""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from app.services.enrichment.constants import (
    MAX_JSONLD_BLOCKS,
    MAX_PAGE_TEXT,
    PAGE_KEYWORDS,
)
from app.services.enrichment.guard import is_social_host, social_field

_WS_RE = re.compile(r"\s+")
_META_REFRESH_RE = re.compile(
    r"""url\s*=\s*['"]?([^'">\s]+)""",
    re.IGNORECASE,
)


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.links: list[dict[str, str]] = []
        self.images: list[dict[str, object]] = []
        self.meta: list[tuple[str, str, str]] = []
        self.jsonld_raw: list[str] = []
        self.lang = ""
        self._skip = 0
        self._in_title = False
        self._in_jsonld = False
        self._jsonld_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = {key.lower(): (value or "") for key, value in attrs}
        if tag == "html" and not self.lang:
            self.lang = data.get("lang", "")[:16]
        if tag in {"script", "style", "noscript"}:
            if tag == "script" and "ld+json" in data.get("type", ""):
                self._in_jsonld = True
                self._jsonld_parts = []
            else:
                self._skip += 1
            return
        if self._skip:
            return
        if tag == "title":
            self._in_title = True
        if tag == "a" and data.get("href"):
            self.links.append({"href": data["href"].strip(), "text": ""})
        if tag == "img" and data.get("src"):
            self.images.append(_image(data, "src"))
        if tag == "meta":
            self.meta.append(
                (
                    data.get("property", "") or data.get("name", ""),
                    data.get("content", ""),
                    data.get("http-equiv", ""),
                )
            )
        if tag in {"p", "br", "li", "h1", "h2", "h3", "div", "tr"}:
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._in_jsonld:
            raw = "".join(self._jsonld_parts).strip()
            if raw and len(self.jsonld_raw) < MAX_JSONLD_BLOCKS:
                self.jsonld_raw.append(raw[:20_000])
            self._in_jsonld = False
            return
        if tag in {"script", "style", "noscript"} and self._skip:
            self._skip -= 1
            return
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_jsonld:
            self._jsonld_parts.append(data)
            return
        if self._skip:
            return
        if self._in_title:
            self.title_parts.append(data)
        if self.links and data.strip():
            self.links[-1]["text"] = (
                self.links[-1]["text"] + " " + data.strip()
            ).strip()[:200]
        self.text_parts.append(data)


def _image(data: dict[str, str], key: str) -> dict[str, object]:
    return {
        "src": data.get(key, ""),
        "alt": data.get("alt", "")[:200],
        "width": _int_or_none(data.get("width")),
        "height": _int_or_none(data.get("height")),
    }


def _int_or_none(value: str | None) -> int | None:
    if not value:
        return None
    digits = "".join(ch for ch in value if ch.isdigit())
    if not digits:
        return None
    return int(digits)


def parse_html(url: str, markup: str) -> dict[str, object]:
    """Parse a page. Links and image URLs are absolute."""
    parser = _PageParser()
    parser.feed(markup or "")
    parser.close()
    text = _WS_RE.sub(" ", " ".join(parser.text_parts)).strip()[:MAX_PAGE_TEXT]
    og: dict[str, str] = {}
    for name, content, _http_equiv in parser.meta:
        key = name.lower().strip()
        if key.startswith("og:") or key in {"description", "twitter:image"}:
            og[key] = content.strip()[:2000]
    images = _collect_images(url, parser.images, og)
    links, social, mailtos, tels = _collect_links(url, parser.links)
    jsonld = _load_jsonld(parser.jsonld_raw)
    return {
        "url": url,
        "title": _WS_RE.sub(" ", " ".join(parser.title_parts)).strip()[:300],
        "lang": parser.lang,
        "text": text,
        "jsonld": jsonld,
        "jsonld_raw": parser.jsonld_raw,
        "og": og,
        "images": images,
        "links": links,
        "social": social,
        "mailtos": mailtos,
        "tels": tels,
        "meta_refresh": _meta_refresh(url, parser.meta),
    }


def page_corpus(page: dict[str, object]) -> str:
    """Text the evidence quote is allowed to come from."""
    parts = [str(page.get("text") or "")]
    parts.extend(str(item) for item in (page.get("jsonld_raw") or []))
    og = page.get("og") or {}
    if isinstance(og, dict):
        parts.extend(str(value) for value in og.values())
    return "\n".join(parts)


def quote_supported(pages: list[dict[str, object]], url: str, quote: str) -> bool:
    needle = (quote or "").strip()
    if len(needle) < 8:
        return False
    for page in pages:
        if str(page.get("final_url") or page.get("url") or "") != url:
            continue
        if needle in page_corpus(page):
            return True
    return False


def link_score(href: str, anchor: str) -> int:
    blob = f"{href} {anchor}".casefold()
    return sum(1 for word in PAGE_KEYWORDS if word.casefold() in blob)


def _collect_links(
    base: str,
    raw_links: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[str], list[str]]:
    links: list[dict[str, str]] = []
    social: list[dict[str, str]] = []
    mailtos: list[str] = []
    tels: list[str] = []
    seen: set[str] = set()
    for item in raw_links:
        href = item.get("href") or ""
        if href.lower().startswith("mailto:"):
            mailtos.append(href.split(":", 1)[1].split("?", 1)[0][:320])
            continue
        if href.lower().startswith("tel:"):
            tels.append(href.split(":", 1)[1][:40])
            continue
        if href.startswith("javascript:"):
            continue
        absolute = urljoin(base, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            continue
        host = parsed.hostname.lower()
        if is_social_host(host):
            field = social_field(host)
            if field:
                social.append({"field": field, "url": absolute[:400]})
            continue
        key = absolute.split("#", 1)[0]
        if key in seen:
            continue
        seen.add(key)
        links.append({"href": key, "text": item.get("text") or ""})
    return links[:80], social, mailtos[:5], tels[:5]


def _collect_images(
    base: str,
    raw_images: list[dict[str, object]],
    og: dict[str, str],
) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    seen: set[str] = set()
    for key in ("og:image", "twitter:image"):
        src = og.get(key)
        if src:
            raw_images.insert(
                0, {"src": src, "alt": key, "width": None, "height": None}
            )
    for item in raw_images:
        src = str(item.get("src") or "")
        absolute = urljoin(base, src)
        if not absolute.startswith(("http://", "https://")):
            continue
        if absolute in seen:
            continue
        width = item.get("width")
        height = item.get("height")
        if _tiny(width, height) or _tracker(absolute):
            continue
        seen.add(absolute)
        found.append(
            {
                "src": absolute[:500],
                "alt": str(item.get("alt") or "")[:200],
                "width": width,
                "height": height,
            }
        )
        if len(found) >= 20:
            break
    return found


def _tiny(width: object, height: object) -> bool:
    if isinstance(width, int) and isinstance(height, int):
        return width < 400 or height < 400
    return False


def _tracker(url: str) -> bool:
    blob = url.casefold()
    return any(token in blob for token in ("pixel", "spacer", "tracking", "1x1"))


def _load_jsonld(raw_blocks: list[str]) -> list[object]:
    loaded: list[object] = []
    for raw in raw_blocks:
        try:
            loaded.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return loaded


def _meta_refresh(base: str, meta: list[tuple[str, str, str]]) -> str:
    for _name, content, http_equiv in meta:
        if http_equiv.lower() != "refresh":
            continue
        match = _META_REFRESH_RE.search(content or "")
        if not match:
            continue
        target = urljoin(base, match.group(1).strip())
        parsed = urlparse(target)
        if parsed.scheme in {"http", "https"} and parsed.hostname:
            return target
    return ""
