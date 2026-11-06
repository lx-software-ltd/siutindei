"""The partner API-key authorizer stays on the search dependency profile.

That profile does not ship PyJWT, phonenumbers, pycountry, pypdf, or
alembic. Importing the handler must not pull those in, and it must not
pull the public search stack either.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_partner_authorizer_cold_import_stays_on_the_core_profile() -> None:
    backend = Path(__file__).resolve().parents[1] / "backend"
    script = """
import importlib.util
import sys

spec = importlib.util.spec_from_file_location(
    "api_key_handler",
    "lambda/authorizers/api_key/handler.py",
)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)
blocked = [
    "jwt",
    "phonenumbers",
    "pycountry",
    "pypdf",
    "alembic",
    "app.api.search",
]
loaded = [name for name in blocked if name in sys.modules]
if loaded:
    raise SystemExit("authorizer loaded " + ", ".join(loaded))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=backend,
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
