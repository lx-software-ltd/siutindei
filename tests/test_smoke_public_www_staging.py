"""Staging smoke reads the origin from the resolve-step output."""

from __future__ import annotations

from pathlib import Path

WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "workflows"
    / "smoke-public-www-staging.yml"
)

ORIGIN = "${{ steps.resolve_public_site_config.outputs.staging_site_origin }}"


def test_smoke_reads_the_resolve_step_origin() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "id: resolve_public_site_config" in text
    assert "resolve_staging_site_origin" not in text
    assert "vars.STAGING_SITE_ORIGIN ||" not in text
    assert f"SMOKE_BASE_URL: {ORIGIN}" in text
    assert f"SUMMARY_TARGET_URL: {ORIGIN}" in text
    before_values, _marker, _rest = text.partition("# template:set")
    assert "SMOKE_BASE_URL:" in before_values
