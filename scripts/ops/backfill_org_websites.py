"""Write organization websites from stored import files.

Reads each completed import that still warns the website was not
stored. A readable file stores the website and then the warning is
removed. A missing file keeps the warning. A website already stored
is left in place.

Run from the repo root with DATABASE_URL and
ADMIN_IMPORT_EXPORT_BUCKET set:

    python3 scripts/ops/backfill_org_websites.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from app.db.engine import get_engine
from app.services.import_website_backfill import (
    backfill_import_websites,
    load_s3_import_payload,
)
from app.utils.logging import get_logger
from sqlalchemy.orm import Session

logger = get_logger(__name__)


def main() -> int:
    """Apply the backfill and commit."""
    if not os.environ.get("ADMIN_IMPORT_EXPORT_BUCKET", "").strip():
        logger.error("ADMIN_IMPORT_EXPORT_BUCKET is required")
        return 1
    engine = get_engine(use_cache=False)
    with Session(engine) as session:
        report = backfill_import_websites(session, load_s3_import_payload)
        session.commit()
    logger.info(
        "Import website backfill finished",
        extra={
            "jobs_seen": report.jobs_seen,
            "websites_written": report.websites_written,
            "warnings_removed": report.warnings_removed,
            "payloads_missing": len(report.payloads_missing),
        },
    )
    for object_key in report.payloads_missing:
        logger.warning(
            "Import file missing; website warning kept",
            extra={"object_key": object_key},
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
