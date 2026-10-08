"""Alembic revision ids stay within varchar(32) and form one chain."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = ROOT / "backend" / "db" / "alembic" / "versions"
REVISION_RE = re.compile(r'^revision:\s*str\s*=\s*"([^"]+)"', re.MULTILINE)
DOWN_RE = re.compile(
    r'^down_revision:\s*Union\[str,\s*None\]\s*=\s*(None|"([^"]+)")',
    re.MULTILINE,
)
ID_RE = re.compile(r"^\d{4}_[a-z0-9_]+$")


def test_revision_ids_and_single_head() -> None:
    revisions: dict[str, str | None] = {}
    for path in sorted(VERSIONS.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        revision_match = REVISION_RE.search(text)
        down_match = DOWN_RE.search(text)
        assert revision_match, path.name
        assert down_match, path.name
        revision = revision_match.group(1)
        assert len(revision) <= 32, revision
        assert ID_RE.match(revision), revision
        assert path.name.startswith(revision), path.name
        parent = down_match.group(2)
        revisions[revision] = parent
    parents = set(revisions.values())
    heads = [revision for revision in revisions if revision not in parents]
    roots = [revision for revision, parent in revisions.items() if parent is None]
    assert len(roots) == 1
    assert roots[0] == "0001_initial_schema"
    assert len(heads) == 1
    for revision, parent in revisions.items():
        if parent is not None:
            assert parent in revisions, revision
