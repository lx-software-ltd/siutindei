"""Tests for board runner path and size policy."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ci" / "board_policy.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("board_policy", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


board_policy = _load_module()


@pytest.mark.parametrize(
    "path",
    [
        ".github/workflows/board-agent.yml",
        "infra/lib/stack.ts",
        "apps/admin_web/src/auth/login.ts",
        "backend/src/payments/stripe.py",
        "backend/db/migrations/0010_add_audit.sql",
    ],
)
def test_protected_paths(path: str) -> None:
    assert board_policy.path_is_protected(path) is True


@pytest.mark.parametrize(
    "path",
    [
        "apps/public_www/src/content/en.json",
        "docs/architecture/overview.md",
        "backend/src/app/services/search.py",
        "AGENTS.md",
    ],
)
def test_unprotected_paths(path: str) -> None:
    assert board_policy.path_is_protected(path) is False


def test_rename_from_protected_path_is_blocked() -> None:
    files = [
        {
            "filename": "docs/moved.md",
            "previous_filename": ".github/workflows/lint.yml",
            "additions": 1,
            "deletions": 1,
            "changes": 2,
        }
    ]
    assert board_policy.evaluate_files(files) == (
        "protected path .github/workflows/lint.yml"
    )


def test_feature_line_limit() -> None:
    files = [
        {
            "filename": "apps/public_www/src/lib/site-config.ts",
            "additions": 250,
            "deletions": 160,
            "changes": 410,
        }
    ]
    assert board_policy.evaluate_files(files, kind="feature") == (
        "pull request changes 410 lines (max 400)"
    )


def test_content_kind_allows_larger_diff() -> None:
    files = [
        {
            "filename": "content/en/guide.md",
            "additions": 1500,
            "deletions": 0,
            "changes": 1500,
        }
    ]
    assert board_policy.evaluate_files(files, kind="content") is None


def test_content_kind_rejects_non_content() -> None:
    files = [
        {
            "filename": "apps/public_www/src/content/en.json",
            "additions": 2,
            "deletions": 0,
            "changes": 2,
        }
    ]
    reason = board_policy.evaluate_files(files, kind="content")
    assert reason is not None
    assert reason.startswith("content kind may only change content/**")


def test_ci_green_with_skipped_checks() -> None:
    runs = [
        {"status": "completed", "conclusion": "success"},
        {"status": "completed", "conclusion": "skipped"},
    ]
    assert board_policy.ci_is_green(runs, "pending") is True


def test_ci_green_when_no_checks_were_requested() -> None:
    assert board_policy.ci_is_green([], "pending") is True
    assert board_policy.ci_is_green([], "") is True
    assert board_policy.ci_is_green([], "success") is True


def test_ci_not_green_when_combined_status_failed() -> None:
    assert board_policy.ci_is_green([], "failure") is False
    assert board_policy.ci_is_green([], "error") is False
