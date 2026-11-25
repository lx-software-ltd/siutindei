"""Staging smoke reads the origin from the resolve-step output."""

from __future__ import annotations

from pathlib import Path

WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "workflows"
    / "smoke-public-www-staging.yml"
)

SMOKE_BASE_URL = (
    "${{ vars.STAGING_SITE_ORIGIN || "
    "steps.resolve_public_site_config.outputs.staging_site_origin }}"
)
SUMMARY_TARGET_URL = (
    "${{ steps.resolve_public_site_config.outputs.staging_site_origin }}"
)


def test_smoke_reads_the_resolve_step_origin() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "id: resolve_public_site_config" in text
    assert "resolve_staging_site_origin" not in text
    assert f"SMOKE_BASE_URL: {SMOKE_BASE_URL}" in text
    assert f"SUMMARY_TARGET_URL: {SUMMARY_TARGET_URL}" in text
    smoke_env = text.split("# template:set", 1)[1].split("# template:end", 1)[0]
    assert "SMOKE_BASE_URL:" in smoke_env
