"""Play upload stays off until PLAY_STORE_UPLOAD_ENABLED is exactly true."""

from __future__ import annotations

from pathlib import Path

WORKFLOW = (
    Path(__file__).resolve().parents[1] / ".github" / "workflows" / "deploy-mobile.yml"
)


def test_play_upload_requires_the_enable_flag() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "upload-enabled: ${{ vars.PLAY_STORE_UPLOAD_ENABLED == 'true' }}" in text
    assert "upload-enabled: ${{ vars.PLAY_STORE_UPLOAD_ENABLED }}" not in text
    assert "if: ${{ steps.playstore.outputs.should_upload == 'true' }}" in text
