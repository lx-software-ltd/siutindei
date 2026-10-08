#!/usr/bin/env python3
"""Fill the board pull request template from the runner environment."""

from __future__ import annotations

import os
from pathlib import Path


def render(
    *,
    brief: str,
    zone: str,
    evidence: str,
    task_id: str,
) -> str:
    evidence_text = evidence.strip() or "No test log was captured."
    return "\n".join(
        [
            "## Intent",
            "",
            brief.rstrip(),
            "",
            "## Zone",
            "",
            zone.strip() or "open",
            "",
            "## Invariants",
            "",
            "Red-zone paths stay unchanged unless this brief is kind content.",
            "Content kind stays inside content/**.",
            "",
            "## Evidence",
            "",
            evidence_text,
            "",
            "## Docs and seed data",
            "",
            "See the brief. Seed data is a red-zone path.",
            "",
            "## Rollback",
            "",
            "Revert the squash commit.",
            "",
            f"Task: {task_id}",
            "",
        ]
    )


def main() -> int:
    brief_path = Path(os.environ["BOARD_BRIEF_FILE"])
    evidence_path = Path(os.environ.get("BOARD_EVIDENCE_FILE", ""))
    evidence = ""
    if evidence_path.is_file():
        lines = evidence_path.read_text(encoding="utf-8").splitlines()
        evidence = "\n".join(lines[-80:])
    print(
        render(
            brief=brief_path.read_text(encoding="utf-8"),
            zone=os.environ.get("BOARD_ZONE", ""),
            evidence=evidence,
            task_id=os.environ.get("BOARD_TASK_ID", ""),
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
