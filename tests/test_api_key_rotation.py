"""API key rotation reads only a JSON object from Secrets Manager."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

HANDLER_PATH = (
    Path(__file__).resolve().parents[1]
    / "backend"
    / "lambda"
    / "api_key_rotation"
    / "handler.py"
)


def _load_handler():
    spec = importlib.util.spec_from_file_location(
        "api_key_rotation_handler", HANDLER_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rotation_handler = _load_handler()


class _Secrets:
    def __init__(self, secret: str | None) -> None:
        self._secret = secret

    def get_secret_value(self, SecretId: str) -> dict[str, str]:
        del SecretId
        if self._secret is None:
            return {}
        return {"SecretString": self._secret}


def test_non_json_secret_is_treated_as_unset() -> None:
    assert (
        rotation_handler._get_old_key_info_from_secret(_Secrets("pending"), "arn")
        is None
    )
    assert rotation_handler._get_old_key_info_from_secret(_Secrets(""), "arn") is None
    assert rotation_handler._get_old_key_info_from_secret(_Secrets(None), "arn") is None


def test_json_array_secret_is_treated_as_unset() -> None:
    assert (
        rotation_handler._get_old_key_info_from_secret(
            _Secrets(json.dumps(["key"])), "arn"
        )
        is None
    )


def test_json_object_secret_is_returned() -> None:
    payload = {"api_key_id": "abc", "rotated_at": "2026-11-02T15:34:00+00:00"}
    assert (
        rotation_handler._get_old_key_info_from_secret(
            _Secrets(json.dumps(payload)), "arn"
        )
        == payload
    )
