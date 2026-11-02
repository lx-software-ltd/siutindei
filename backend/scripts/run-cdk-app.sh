#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

ensure_staging_search_fixture() {
  local dest="${SCRIPT_DIR}/../fixtures/activity_search_staging.json"
  local src="${REPO_ROOT}/shared/fixtures/activity_search_staging.json"
  local sync_script="${REPO_ROOT}/scripts/codegen/sync-activity-search-staging-fixture.sh"

  if [ -f "$dest" ]; then
    return 0
  fi

  if [ -f "$sync_script" ] && [ -f "$src" ]; then
    if ! grep -q 'git-lfs.github.com/spec' "$src" 2>/dev/null; then
      bash "$sync_script" backend
      return 0
    fi
  fi

  if [ -f "$src" ] && ! grep -q 'git-lfs.github.com/spec' "$src" 2>/dev/null; then
    mkdir -p "$(dirname "$dest")"
    cp "$src" "$dest"
    return 0
  fi

  # Allow CDK synth/checkov when LFS objects are not pulled (deploy syncs real file).
  mkdir -p "$(dirname "$dest")"
  printf '%s\n' \
    '{"version":1,"meta":{"area_descendants":{},"item_count":0},"items":[]}' \
    >"$dest"
}

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

  echo "Python 3.12 is required for Lambda bundling." >&2
  return 1
}

ensure_staging_search_fixture

PYTHON_BIN="$(resolve_python312)"
"$PYTHON_BIN" "$SCRIPT_DIR/build_lambda_bundle.py"
"$PYTHON_BIN" "$SCRIPT_DIR/build_lambda_bundle.py" --profile search
cd "$SCRIPT_DIR/../infrastructure"
npx ts-node --prefer-ts-exts bin/app.ts
