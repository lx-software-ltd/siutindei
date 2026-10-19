"""Retry transient PyPI failures while building the Lambda dependency cache."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_BUNDLE_PATH = (
    Path(__file__).resolve().parents[1]
    / "backend"
    / "scripts"
    / "build_lambda_bundle.py"
)


def _load_bundle():
    spec = importlib.util.spec_from_file_location("build_lambda_bundle", _BUNDLE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def bundle():
    return _load_bundle()


def test_run_pip_captures_stderr_for_retry_classification(bundle, tmp_path) -> None:
    command = [
        sys.executable,
        "-c",
        "import sys; sys.stderr.write('json.decoder.JSONDecodeError: boom\\n'); raise SystemExit(2)",
    ]
    with pytest.raises(bundle.PipCommandError) as exc_info:
        bundle._run_pip(command, tmp_path, {})
    assert exc_info.value.returncode == 2
    assert bundle._pip_output_is_retryable(exc_info.value.output)


def test_truncated_pypi_json_is_retryable(bundle) -> None:
    output = (
        "json.decoder.JSONDecodeError: Unterminated string starting at: "
        "line 1 column 1330009 (char 1330008)"
    )
    assert bundle._pip_output_is_retryable(output)
    assert not bundle._pip_output_is_retryable(
        "ERROR: No matching distribution found for alembic"
    )


def _install_calls(calls: list[list[str]]) -> list[list[str]]:
    return [command for command in calls if "-r" in command]


def test_dependency_install_retries_truncated_index(
    bundle, tmp_path, monkeypatch
) -> None:
    source = tmp_path / "backend"
    source.mkdir()
    requirements = source / "requirements.txt"
    requirements.write_text("alembic==1.20.0\n", encoding="utf-8")
    cache_dir = tmp_path / "deps-cache" / "abc"
    calls: list[list[str]] = []
    sleeps: list[int] = []

    def fake_run(command: list[str], cwd: Path, env: dict[str, str]) -> None:
        del cwd, env
        calls.append(command)
        if "-r" not in command or len(_install_calls(calls)) != 1:
            return
        target = Path(command[command.index("-t") + 1])
        (target / "partial.txt").write_text("partial", encoding="utf-8")
        raise bundle.PipCommandError(
            command,
            2,
            "json.decoder.JSONDecodeError: Unterminated string starting at: "
            "line 1 column 1330009 (char 1330008)",
        )

    monkeypatch.setattr(bundle, "_run_pip", fake_run)
    monkeypatch.setattr(bundle.time, "sleep", lambda seconds: sleeps.append(seconds))

    bundle._build_dependency_cache(source, requirements, cache_dir, {})

    assert len(_install_calls(calls)) == 2
    assert sleeps == [2]
    assert cache_dir.is_dir()
    assert not (cache_dir / "partial.txt").exists()


def test_dependency_install_does_not_retry_resolution_errors(
    bundle, tmp_path, monkeypatch
) -> None:
    source = tmp_path / "backend"
    source.mkdir()
    requirements = source / "requirements.txt"
    requirements.write_text("alembic==1.20.0\n", encoding="utf-8")
    cache_dir = tmp_path / "deps-cache" / "abc"
    calls: list[list[str]] = []
    sleeps: list[int] = []

    def fake_run(command: list[str], cwd: Path, env: dict[str, str]) -> None:
        del cwd, env
        calls.append(command)
        if "-r" in command:
            raise bundle.PipCommandError(
                command,
                1,
                "ERROR: No matching distribution found for alembic",
            )

    monkeypatch.setattr(bundle, "_run_pip", fake_run)
    monkeypatch.setattr(bundle.time, "sleep", lambda seconds: sleeps.append(seconds))

    with pytest.raises(bundle.PipCommandError):
        bundle._build_dependency_cache(source, requirements, cache_dir, {})

    assert len(_install_calls(calls)) == 1
    assert sleeps == []


def test_dependency_install_stops_after_retry_budget(
    bundle, tmp_path, monkeypatch
) -> None:
    source = tmp_path / "backend"
    source.mkdir()
    requirements = source / "requirements.txt"
    requirements.write_text("alembic==1.20.0\n", encoding="utf-8")
    cache_dir = tmp_path / "deps-cache" / "abc"
    calls: list[list[str]] = []
    sleeps: list[int] = []

    def fake_run(command: list[str], cwd: Path, env: dict[str, str]) -> None:
        del cwd, env
        calls.append(command)
        if "-r" in command:
            raise bundle.PipCommandError(
                command,
                2,
                "json.decoder.JSONDecodeError: Unterminated string",
            )

    monkeypatch.setattr(bundle, "_run_pip", fake_run)
    monkeypatch.setattr(bundle.time, "sleep", lambda seconds: sleeps.append(seconds))

    with pytest.raises(bundle.PipCommandError):
        bundle._build_dependency_cache(source, requirements, cache_dir, {})

    assert len(_install_calls(calls)) == bundle.PIP_INSTALL_ATTEMPTS
    assert sleeps == [2, 4]
