#!/usr/bin/env python3
"""Record that the sessionStart hook ran, when the runner asked for a marker."""

from __future__ import annotations

import os
from pathlib import Path


def main() -> int:
    marker = os.environ.get("CURSOR_HOOK_MARKER", "").strip()
    if marker:
        path = Path(marker)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("sessionStart\n", encoding="utf-8")
    print("{}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
