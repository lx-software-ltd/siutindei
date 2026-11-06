"""Read up to four leaflet files into pages the extract stage already understands."""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Callable
from typing import Any
from uuid import UUID, uuid4

from botocore.exceptions import ClientError

from app.exceptions import ValidationError
from app.services.enrichment.constants import (
    MAX_IMAGE_BYTES,
    MAX_LEAFLETS,
    MAX_PAGE_TEXT,
    MAX_PDF_BYTES,
    MAX_PDF_VISION_PAGES,
    MAX_VISION_IMAGES,
    MIN_PDF_TEXT_CHARS,
)
from app.services.enrichment.guard import CrawlError, validate_seed_url

FetchUrl = Callable[[str, str], dict[str, Any]]
ReadObject = Callable[[str], bytes]
PutImage = Callable[[str, bytes, str], str]

_ALLOWED_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
}
_EXT_TYPES = {ext: ctype for ctype, ext in _ALLOWED_TYPES.items()}
_EXT_TYPES[".jpeg"] = "image/jpeg"
_NAME_RE = re.compile(r"[^A-Za-z0-9._-]")
_MISSING_OBJECT = {"404", "NoSuchKey", "NotFound"}


class LeafletReadError(Exception):
    """The leaflet cannot be read. The run fails without a retry."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def sniff_leaflet(body: bytes) -> tuple[str, str] | None:
    """Extension and content type from the file bytes, or None."""
    if body.startswith(b"%PDF"):
        return "pdf", "application/pdf"
    if body.startswith(b"\xff\xd8\xff"):
        return "jpg", "image/jpeg"
    if body.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png", "image/png"
    if len(body) >= 12 and body[:4] == b"RIFF" and body[8:12] == b"WEBP":
        return "webp", "image/webp"
    return None


def leaflet_prefix(org_id: UUID | str) -> str:
    return f"organizations/{org_id}/enrichment/leaflets/"


def valid_leaflet_key(org_id: UUID | str, key: str) -> bool:
    prefix = leaflet_prefix(org_id)
    if not key.startswith(prefix):
        return False
    name = key[len(prefix) :]
    if not name or "/" in name or ".." in name:
        return False
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,140}", name):
        return False
    return _extension(name) in _EXT_TYPES


def presign_leaflet(org_id: UUID, file_name: str, content_type: str) -> dict[str, Any]:
    """Presigned PUT for one leaflet. The key stays under this organization."""
    ctype = content_type.split(";", 1)[0].strip().lower()
    ext = _ALLOWED_TYPES.get(ctype)
    if ext is None:
        raise ValidationError(
            "leaflet must be a JPEG, PNG, WebP, or PDF",
            field="content_type",
        )
    if not str(file_name or "").strip():
        raise ValidationError("file_name is required", field="file_name")
    cleaned = _NAME_RE.sub("_", str(file_name).strip()) or "leaflet"
    base, _old = os.path.splitext(cleaned)
    trimmed = base[:40].strip("_") or "leaflet"
    key = f"{leaflet_prefix(org_id)}{uuid4().hex}-{trimmed}{ext}"
    bucket = _bucket()
    base_url = _base_url()
    from app.services.aws_clients import get_s3_client

    upload_url = get_s3_client().generate_presigned_url(
        "put_object",
        Params={"Bucket": bucket, "Key": key, "ContentType": ctype},
        ExpiresIn=900,
    )
    return {
        "upload_url": upload_url,
        "media_url": f"{base_url}/{key}",
        "object_key": key,
        "content_type": ctype,
        "expires_in": 900,
    }


def normalize_leaflet_items(org_id: UUID, raw: object) -> list[dict[str, Any]]:
    """One to four URL or uploaded-file items. Uploads are checked with HEAD."""
    items = _raw_items(raw)
    if not items or len(items) > MAX_LEAFLETS:
        raise ValidationError(
            f"Send 1 to {MAX_LEAFLETS} leaflets",
            field="leaflet",
        )
    prepared: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValidationError("each leaflet must be an object", field="leaflet")
        url = item.get("url")
        key = item.get("object_key")
        if bool(url) == bool(key):
            raise ValidationError(
                "each leaflet needs a url or an object_key",
                field="leaflet",
            )
        if isinstance(url, str):
            prepared.append(_url_item(url))
            continue
        if not isinstance(key, str) or not valid_leaflet_key(org_id, key):
            raise ValidationError(
                "leaflet file does not match the organization",
                field="object_key",
            )
        prepared.append(_object_item(key))
    return prepared


def read_leaflets(
    org_id: UUID | str,
    items: list[dict[str, Any]],
    *,
    fetch_url: FetchUrl | None = None,
    read_object: ReadObject | None = None,
    put_image: PutImage | None = None,
) -> dict[str, Any]:
    """Store URL leaflets, then shape one page per file.

    Pictures, and scanned PDFs, keep ``vision_urls`` for the next stage.
    A text PDF does not.
    """
    fetch = fetch_url or _proxy_fetch
    read = read_object or _read_object
    store_image = put_image or _put_image
    pages: list[dict[str, Any]] = []
    stored: list[dict[str, Any]] = []
    total = 0
    vision_room = MAX_VISION_IMAGES
    for item in items:
        loaded, total = _load_one(
            org_id,
            item,
            fetch=fetch,
            read=read,
            total=total,
        )
        page, used = _page_for(org_id, loaded, store_image, vision_room)
        vision_room -= used
        pages.append(page)
        stored.append(loaded["item"])
    if not pages:
        raise LeafletReadError("The leaflet has no readable text")
    if not _needs_vision(pages) and not any(
        str(page.get("text") or "").strip() for page in pages
    ):
        raise LeafletReadError("The leaflet has no readable text")
    return {"pages": pages, "items": stored, "bytes_fetched": total}


def _needs_vision(pages: list[dict[str, Any]]) -> bool:
    return any(page.get("vision_urls") for page in pages)


def _load_one(
    org_id: UUID | str,
    item: dict[str, Any],
    *,
    fetch: FetchUrl,
    read: ReadObject,
    total: int,
) -> tuple[dict[str, Any], int]:
    current = dict(item)
    if current.get("kind") == "url":
        fetched = fetch(str(current.get("url") or ""), str(org_id))
        key = str(fetched.get("key") or "")
        if not valid_leaflet_key(org_id, key):
            raise LeafletReadError("The leaflet could not be read")
        current = {
            "kind": "object",
            "key": key,
            "url": str(fetched.get("url") or ""),
            "content_type": str(fetched.get("content_type") or ""),
            "name": _name_from_url(str(item.get("url") or "")),
        }
    key = str(current.get("key") or "")
    try:
        body = read(key)
    except LeafletReadError:
        raise
    except Exception as exc:
        raise LeafletReadError("The leaflet file is missing") from exc
    sniffed = sniff_leaflet(body)
    if sniffed is None:
        raise LeafletReadError("leaflet must be a picture or a PDF")
    ext, ctype = sniffed
    limit = MAX_PDF_BYTES if ext == "pdf" else MAX_IMAGE_BYTES
    if len(body) > limit:
        raise LeafletReadError("The leaflet is too large")
    current["content_type"] = ctype
    current["url"] = str(current.get("url") or f"{_base_url()}/{key}")
    return {"item": current, "body": body, "content_type": ctype}, total + len(body)


def _page_for(
    org_id: UUID | str,
    loaded: dict[str, Any],
    put_image: PutImage,
    vision_room: int,
) -> tuple[dict[str, Any], int]:
    item = loaded["item"]
    body = loaded["body"]
    ctype = str(loaded["content_type"])
    url = str(item.get("url") or "")
    name = str(item.get("name") or "Leaflet")
    page = _empty_page(url)
    used = 0
    if ctype == "application/pdf":
        text = _pdf_text(url, body)
        images: list[str] = []
        if len(text) < MIN_PDF_TEXT_CHARS and vision_room > 0:
            images, used = _pdf_vision_urls(
                org_id,
                body,
                put_image,
                min(MAX_PDF_VISION_PAGES, vision_room),
            )
        page["text"] = text[:MAX_PAGE_TEXT]
        if images:
            page["vision_urls"] = images
        return page, used
    if vision_room > 0:
        page["vision_urls"] = [url]
        used = 1
    page["leaflet_media"] = {
        "source_url": url,
        "object_key": str(item.get("key") or ""),
        "label": f"Leaflet · {name}"[:120],
    }
    return page, used


def _pdf_text(url: str, body: bytes) -> str:
    from app.services.enrichment.pdf import parse_pdf

    parsed = parse_pdf(url, body)
    if not isinstance(parsed, dict):
        return ""
    return str(parsed.get("text") or "")


def _pdf_vision_urls(
    org_id: UUID | str,
    body: bytes,
    put_image: PutImage,
    limit: int,
) -> tuple[list[str], int]:
    from app.services.enrichment.pdf import pdf_page_images

    urls: list[str] = []
    for blob in pdf_page_images(body, limit=limit):
        sniffed = sniff_leaflet(blob)
        if sniffed is None or sniffed[0] == "pdf":
            continue
        ext, ctype = sniffed
        digest = hashlib.sha256(blob).hexdigest()[:16]
        key = f"{leaflet_prefix(org_id)}{digest}.{ext}"
        urls.append(put_image(key, blob, ctype))
    return urls, len(urls)


def _empty_page(url: str) -> dict[str, Any]:
    return {
        "url": url,
        "final_url": url,
        "status": 200,
        "title": "",
        "lang": "",
        "text": "",
        "jsonld": [],
        "jsonld_raw": [],
        "og": {},
        "images": [],
        "links": [],
        "social": [],
        "mailtos": [],
        "tels": [],
    }


def _proxy_fetch(url: str, org_id: str) -> dict[str, Any]:
    from app.services.aws_proxy import crawl_invoke

    fetched = crawl_invoke({"op": "leaflet", "url": url, "org_id": org_id})
    if not isinstance(fetched, dict):
        raise LeafletReadError("The leaflet could not be read")
    return fetched


def _read_object(key: str) -> bytes:
    from app.services.aws_clients import get_s3_client

    try:
        response = get_s3_client().get_object(Bucket=_bucket(), Key=key)
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code in _MISSING_OBJECT:
            raise LeafletReadError("The leaflet file is missing") from exc
        raise
    body = response["Body"].read()
    return body if isinstance(body, bytes) else bytes(body)


def _put_image(key: str, body: bytes, content_type: str) -> str:
    from app.services.aws_clients import get_s3_client

    get_s3_client().put_object(
        Bucket=_bucket(),
        Key=key,
        Body=body,
        ContentType=content_type,
    )
    return f"{_base_url()}/{key}"


def _raw_items(raw: object) -> list[object]:
    if isinstance(raw, list):
        return list(raw)
    if isinstance(raw, dict) and isinstance(raw.get("items"), list):
        return list(raw["items"])
    if isinstance(raw, dict) and ("url" in raw or "object_key" in raw):
        return [raw]
    raise ValidationError("leaflet must list files or URLs", field="leaflet")


def _url_item(url: str) -> dict[str, Any]:
    try:
        seed = validate_seed_url(url)
    except CrawlError as exc:
        raise ValidationError(str(exc), field="url") from exc
    return {"kind": "url", "url": seed, "name": _name_from_url(seed)}


def _object_item(key: str) -> dict[str, Any]:
    head = head_leaflet(key)
    ctype = str(head.get("content_type") or "").split(";", 1)[0].strip().lower()
    expected = _EXT_TYPES.get(_extension(key))
    if ctype != expected:
        raise ValidationError(
            "leaflet must be a picture or a PDF",
            field="content_type",
        )
    length = int(head.get("content_length") or 0)
    limit = MAX_PDF_BYTES if ctype == "application/pdf" else MAX_IMAGE_BYTES
    if length <= 0 or length > limit:
        raise ValidationError("The leaflet is too large", field="object_key")
    return {
        "kind": "object",
        "key": key,
        "url": f"{_base_url()}/{key}",
        "content_type": ctype,
        "name": key.rsplit("/", 1)[-1],
    }


def head_leaflet(key: str) -> dict[str, Any]:
    from app.services.aws_clients import get_s3_client

    try:
        response = get_s3_client().head_object(Bucket=_bucket(), Key=key)
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code in _MISSING_OBJECT:
            raise ValidationError(
                "The leaflet file is missing",
                field="object_key",
            ) from exc
        raise
    return {
        "content_type": str(response.get("ContentType") or ""),
        "content_length": int(response.get("ContentLength") or 0),
    }


def _bucket() -> str:
    value = os.getenv("ORGANIZATION_MEDIA_BUCKET", "").strip()
    if not value:
        raise ValidationError("media bucket is not configured", field="leaflet")
    return value


def _base_url() -> str:
    value = os.getenv("ORGANIZATION_MEDIA_BASE_URL", "").rstrip("/")
    if not value:
        raise ValidationError("media bucket is not configured", field="leaflet")
    return value


def _extension(name: str) -> str:
    return os.path.splitext(name)[1].lower()


def _name_from_url(url: str) -> str:
    path = url.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1]
    return path or "leaflet"
