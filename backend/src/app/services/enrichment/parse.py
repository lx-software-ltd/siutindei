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
    SKIP_KEYWORDS,
)
from app.services.enrichment.guard import is_social_host, social_field

_WS_RE = re.compile(r"\s+")
_CAMEL_RE = re.compile(r"(?<=[a-z])(?=[A-Z])")
_LOCALE_RE = re.compile(r"^(?:[a-z]{2}(?:[-_][a-z]{2,4})?|tc|sc|chs|cht)$", re.I)
_QUOTE_FOLD = str.maketrans(
    {"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "\xa0": " "}
)
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
        self.icons: list[dict[str, str]] = []
        self.meta: list[tuple[str, str, str]] = []
        self.jsonld_raw: list[str] = []
        self.lang = ""
        self._skip = 0
        self._nav = 0
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
        if tag == "nav":
            self._nav += 1
        if tag == "title":
            self._in_title = True
        if tag == "a" and data.get("href"):
            self.links.append({"href": data["href"].strip(), "text": ""})
        if tag == "img" and data.get("src"):
            self.images.append(_image(data, "src"))
        if tag == "link" and data.get("href") and _icon_rel(data.get("rel", "")):
            self.icons.append(
                {"href": data["href"].strip(), "rel": data.get("rel", "")}
            )
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
        if tag == "nav" and self._nav:
            self._nav -= 1
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
        if not self._nav:
            self.text_parts.append(data)


def _icon_rel(rel: str) -> bool:
    folded = rel.casefold()
    return "icon" in folded or "logo" in folded


def _image(data: dict[str, str], key: str) -> dict[str, object]:
    return {
        "src": data.get(key, ""),
        "alt": data.get("alt", "")[:200],
        "class": data.get("class", "")[:200],
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
    icons = _collect_icons(url, parser.icons)
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
        "icons": icons,
        "links": links,
        "social": social,
        "mailtos": mailtos,
        "tels": tels,
        "meta_refresh": _meta_refresh(url, parser.meta),
    }


def page_corpus(page: dict[str, object]) -> str:
    """Text the evidence quote is allowed to come from."""
    parts = [str(page.get("text") or "")]
    jsonld_raw = page.get("jsonld_raw")
    if isinstance(jsonld_raw, list):
        parts.extend(str(item) for item in jsonld_raw)
    og = page.get("og") or {}
    if isinstance(og, dict):
        parts.extend(str(value) for value in og.values())
    return "\n".join(parts)


def page_url(page: dict[str, object]) -> str:
    return str(page.get("final_url") or page.get("url") or "")


def find_quote(pages: list[dict[str, object]], url: str, quote: str) -> str | None:
    """URL of the fetched page holding the quote, trying the cited page first.

    Spacing, case, curly quotes, and the URL's www, scheme, or trailing slash
    do not matter.
    """
    needle = _fold(quote)
    if len(needle) < 8:
        return None
    cited = url_key(url) if url else ""
    ordered = sorted(pages, key=lambda page: url_key(page_url(page)) != cited)
    for page in ordered:
        if needle in _fold(page_corpus(page)):
            return page_url(page)
    return None


def quote_supported(pages: list[dict[str, object]], url: str, quote: str) -> bool:
    return find_quote(pages, url, quote) is not None


def url_key(url: str) -> str:
    """One key per page, whatever the scheme, www, trailing slash, or fragment."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().removeprefix("www.")
    key = host + parsed.path.rstrip("/")
    return f"{key}?{parsed.query}" if parsed.query else key


def link_score(href: str, anchor: str, base: str = "") -> int:
    """Keywords add one each. A skip word or another language's copy costs more.

    A linked PDF on these sites is usually a timetable, fee sheet, or term
    flyer, so it starts ahead of a plain menu page.
    """
    path = urlparse(href).path
    blob = _CAMEL_RE.sub(" ", f"{path} {anchor}").casefold()
    score = 2 if path.lower().endswith(".pdf") else 0
    score += sum(1 for word in PAGE_KEYWORDS if _has_word(blob, word))
    score -= 3 * sum(1 for word in SKIP_KEYWORDS if _has_word(blob, word))
    if base and _locale(href) != _locale(base):
        score -= 2
    return score


def _has_word(blob: str, word: str) -> bool:
    # Short words need a word start, so "workshop" is not "shop".
    if not word.isascii() or len(word) >= 6:
        return word in blob
    return re.search(rf"(?<![a-z]){re.escape(word)}", blob) is not None


def _locale(url: str) -> str:
    first = urlparse(url).path.strip("/").split("/", 1)[0]
    return first.lower().replace("-", "_") if _LOCALE_RE.match(first) else ""


def _fold(text: str) -> str:
    return _WS_RE.sub(" ", (text or "").translate(_QUOTE_FOLD)).strip().casefold()


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
                0, {"src": src, "alt": key, "class": "", "width": None, "height": None}
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
                "class": str(item.get("class") or "")[:200],
                "width": width,
                "height": height,
            }
        )
        if len(found) >= 20:
            break
    return found


def _collect_icons(base: str, raw_icons: list[dict[str, str]]) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in raw_icons:
        absolute = urljoin(base, item.get("href") or "")
        if not absolute.startswith(("http://", "https://")) or absolute in seen:
            continue
        seen.add(absolute)
        found.append({"href": absolute[:500], "rel": (item.get("rel") or "")[:80]})
    return found[:10]


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
