#!/usr/bin/env python3
"""Write one digest per activity in a public catalogue snapshot.

The snapshot is rewritten every hour with a new ``generated_at``, so the
file hash changes even when no activity did. The digests cover the rows
only. The daily production refresh compares them with the digests of the
live build to skip unchanged days, and IndexNow pings only the activity
pages whose digest changed.

Usage: catalogue_snapshot_digests.py SNAPSHOT_JSON OUTPUT_JSON
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def activity_digests(snapshot: dict[str, Any]) -> dict[str, str]:
    """Map each activity id to a sha256 over its rows, in a stable order."""
    rows: dict[str, list[str]] = defaultdict(list)
    for item in snapshot.get("items") or []:
        rows[str(item["activity"]["id"])].append(_canonical(item))
    return {
        activity_id: hashlib.sha256(
            "\n".join(sorted(encoded)).encode("utf-8")
        ).hexdigest()
        for activity_id, encoded in sorted(rows.items())
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2
    snapshot = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    digests = activity_digests(snapshot)
    Path(argv[1]).write_text(_canonical(digests) + "\n", encoding="utf-8")
    print(f"Wrote digests for {len(digests)} activities.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
