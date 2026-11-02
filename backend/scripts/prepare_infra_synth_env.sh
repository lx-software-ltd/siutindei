#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

resolve_python312() {
  if command -v python3.12 >/dev/null 2>&1; then
    echo "python3.12"
    return
  fi

  if command -v python3 >/dev/null 2>&1; then
    if python3 - <<'PY'
import sys
raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)
PY
    then
      echo "python3"
      return
    fi
  fi

  echo "Python 3.12 is required for Lambda dependency cache warmup." >&2
  return 1
}

cd "$REPO_ROOT/backend/infrastructure"
npm ci

PYTHON_BIN="$(resolve_python312)"
"$PYTHON_BIN" "$REPO_ROOT/backend/scripts/build_lambda_bundle.py" \
  --source-root "$REPO_ROOT/backend" \
  --deps-only
"$PYTHON_BIN" "$REPO_ROOT/backend/scripts/build_lambda_bundle.py" \
  --source-root "$REPO_ROOT/backend" \
  --profile search \
  --deps-only
