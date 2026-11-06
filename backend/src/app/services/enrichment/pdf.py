"""Text from a PDF on the provider website, shaped like a parsed HTML page."""

from __future__ import annotations

import io
import re
import time
from collections.abc import Callable

from app.services.enrichment.constants import (
    MAX_IMAGE_BYTES,
    MAX_PAGE_TEXT,
    MAX_PDF_PAGES,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)

_WS_RE = re.compile(r"\s+")


def pdf_page_images(body: bytes, *, limit: int) -> list[bytes]:
    """Largest embedded image on each of the first pages that has one.

    A broken file, or an image pypdf cannot decode, contributes nothing.
    Pillow is installed so filters that need it still decode.
    """
    from pypdf import PdfReader

    found: list[bytes] = []
    try:
        reader = PdfReader(io.BytesIO(body))
        if reader.is_encrypted and not reader.decrypt(""):
            return []
        pages = list(reader.pages)
    except Exception:
        logger.info("skipping images in an unreadable PDF", exc_info=True)
        return []
    for page in pages:
        if len(found) >= limit:
            break
        best = _largest_image(page)
        if best:
            found.append(best)
    return found


def _largest_image(page: object) -> bytes:
    try:
        images = list(getattr(page, "images", []) or [])
    except Exception:
        logger.info("skipping one PDF page's images", exc_info=True)
        return b""
    best = b""
    for image in images:
        try:
            data = bytes(getattr(image, "data", b"") or b"")
        except Exception:
            logger.info("skipping one PDF image", exc_info=True)
            continue
        if MAX_IMAGE_BYTES >= len(data) > len(best):
            best = data
    return best


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
        logger.info("skipping unreadable PDF", exc_info=True)
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
