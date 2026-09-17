"""CLI contract for scripts/ops/board-importer."""

from __future__ import annotations

import subprocess
from pathlib import Path

CLI = Path(__file__).resolve().parents[1] / "scripts" / "ops" / "board-importer"


def test_board_importer_help() -> None:
    result = subprocess.run(
        [str(CLI), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "setup" in result.stdout
    assert "list-managers" in result.stdout
    assert "rotate-password" in result.stdout
    assert "apply-params" not in result.stdout
    assert "--enable-import" not in result.stdout


def test_board_importer_rejects_enable_import() -> None:
    result = subprocess.run(
        [str(CLI), "setup", "--enable-import"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "not supported" in result.stderr
    assert "production.json" in result.stderr


def test_board_importer_rejects_apply_params() -> None:
    result = subprocess.run(
        [str(CLI), "apply-params", "--manager-id", "x"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "Unknown argument: apply-params" in result.stderr
