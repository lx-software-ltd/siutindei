"""Copy organization media keys onto the survivor during a merge."""

from __future__ import annotations

import os
from urllib.parse import urlparse

from app.utils.logging import get_logger

logger = get_logger(__name__)


def copy_merged_media(url: str | None, source_id: str, survivor_id: str) -> str:
    """Copy an S3 object when the bucket is configured; otherwise keep the URL."""
    if not url:
        return ""
    bucket = os.environ.get("ORGANIZATION_MEDIA_BUCKET")
    base = os.environ.get("ORGANIZATION_MEDIA_BASE_URL", "").rstrip("/")
    if not bucket or not base:
        return url
    parsed = urlparse(url)
    if parsed.netloc != urlparse(base).netloc:
        return url
    key = parsed.path.lstrip("/")
    prefix = f"organizations/{source_id}/"
    if not key.startswith(prefix):
        return url
    new_key = f"organizations/{survivor_id}/{key[len(prefix) :]}"
    try:
        from app.services.aws_clients import get_s3_client

        client = get_s3_client()
        client.copy_object(
            Bucket=bucket,
            Key=new_key,
            CopySource={"Bucket": bucket, "Key": key},
        )
        client.delete_object(Bucket=bucket, Key=key)
    except Exception:
        logger.warning("Organization media copy failed")
        return url
    return f"{base}/{new_key}"
