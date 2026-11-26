"""Matcher tests for the public website bundle check."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_public_www_bundle.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_public_www_bundle", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


bundle_check = _load()


def test_bundle_matcher_flags_removed_paths() -> None:
    bundle = 'fetch("/v1/activities/search");const root="/www/assets"'
    assert bundle_check.bundle_offenders(bundle) == (
        "/v1/activities/search",
        "/www/",
    )


def test_bundle_matcher_accepts_the_current_search_path() -> None:
    bundle = 'fetch("/api/v1/public/activities/search")'
    assert bundle_check.bundle_offenders(bundle) == ()


def test_script_urls_find_the_bundle() -> None:
    html = (
        '<html><script src="/_next/static/chunks/main-abc.js"></script>'
        '<script src="/keep.json"></script></html>'
    )
    assert bundle_check.script_urls(html) == ["/_next/static/chunks/main-abc.js"]


def test_refuses_a_non_https_origin(monkeypatch, capsys) -> None:
    monkeypatch.setenv(bundle_check.ORIGIN_ENV, "file:///etc/passwd")

    def boom(*_args, **_kwargs):
        raise AssertionError("a non-https origin must not be opened")

    monkeypatch.setattr(bundle_check.urllib.request, "urlopen", boom)
    assert bundle_check.main() == 1
    error = capsys.readouterr().err
    assert "not https" in error
    assert "file:///etc/passwd" in error


def test_skips_when_the_origin_is_unset(monkeypatch, capsys) -> None:
    monkeypatch.delenv(bundle_check.ORIGIN_ENV, raising=False)

    def boom(*_args, **_kwargs):
        raise AssertionError("the skipped check must not download")

    monkeypatch.setattr(bundle_check.urllib.request, "urlopen", boom)
    assert bundle_check.main() == 0
    output = capsys.readouterr().out
    assert "check skipped" in output
    assert bundle_check.ORIGIN_ENV in output
