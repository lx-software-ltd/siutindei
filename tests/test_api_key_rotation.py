"""API key rotation reads only a JSON object from Secrets Manager."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROTATION_DIR = (
    Path(__file__).resolve().parents[1] / "backend" / "lambda" / "api_key_rotation"
)
sys.path.insert(0, str(ROTATION_DIR))

import handler as rotation_handler


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
