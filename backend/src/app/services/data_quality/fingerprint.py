"""Stable hashes for data-quality inputs."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def fingerprint(payload: dict[str, Any]) -> str:
    """Hash a JSON object so key order and spacing do not change the result."""
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(raw.encode()).hexdigest()
