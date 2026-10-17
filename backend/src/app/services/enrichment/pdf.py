"""Text from a PDF on the provider website, shaped like a parsed HTML page."""

from __future__ import annotations

import io
import re
import time
from typing import Callable

from app.services.enrichment.constants import MAX_PAGE_TEXT, MAX_PDF_PAGES

_WS_RE = re.compile(r"\s+")


def parse_pdf(
    url: str,
    body: bytes,
    *,
    deadline: float | None = None,
    now: Callable[[], float] = time.monotonic,
) -> dict[str, object] | None:
    """Text from the first pages, or None for a broken, locked, or image-only PDF."""
    from pypdf import PdfReader

    parts: list[str] = []
    used = 0
    try:
        reader = PdfReader(io.BytesIO(body))
        if reader.is_encrypted and not reader.decrypt(""):
            return None
        for index, page in enumerate(reader.pages):
            if index >= MAX_PDF_PAGES or used >= MAX_PAGE_TEXT:
                break
            if deadline is not None and now() >= deadline:
                break
            text = page.extract_text() or ""
            parts.append(text)
            used += len(text)
        metadata = reader.metadata
        title = str(metadata.title or "") if metadata is not None else ""
    except Exception:
        # pypdf raises many error types on malformed files; any of them means skip.
        return None
    text = _WS_RE.sub(" ", " ".join(parts)).strip()[:MAX_PAGE_TEXT]
    if not text:
        return None
    return {
        "url": url,
        "title": _WS_RE.sub(" ", title).strip()[:300],
        "lang": "",
        "text": text,
        "jsonld": [],
        "jsonld_raw": [],
        "og": {},
        "images": [],
        "links": [],
        "social": [],
        "mailtos": [],
        "tels": [],
        "meta_refresh": "",
    }
