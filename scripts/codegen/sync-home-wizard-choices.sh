#!/usr/bin/env bash
# Copy canonical home wizard choices into public www and the Flutter asset.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CANONICAL="${ROOT}/shared/home_wizard/home_wizard_choices.json"
TARGET="${ROOT}/apps/public_www/src/data/home_wizard_choices.json"
FLUTTER="${ROOT}/apps/siutindei_app/assets/home_wizard/home_wizard_choices.json"

if [ ! -f "$CANONICAL" ]; then
  echo "sync-home-wizard-choices: missing canonical file at $CANONICAL"
  exit 1
fi

if [ "${1:-}" = "--check" ]; then
  out_of_sync=0
  if ! diff -q "$CANONICAL" "$TARGET" >/dev/null 2>&1; then
    echo "apps/public_www home_wizard_choices.json is out of sync"
    out_of_sync=1
  fi
  if ! diff -q "$CANONICAL" "$FLUTTER" >/dev/null 2>&1; then
    echo "Flutter home_wizard_choices.json is out of sync"
    out_of_sync=1
  fi
  if [ "$out_of_sync" -ne 0 ]; then
    echo "Run: bash scripts/codegen/sync-home-wizard-choices.sh"
    exit 1
  fi
  echo "home_wizard_choices.json is in sync."
  exit 0
fi

cp "$CANONICAL" "$TARGET"
mkdir -p "$(dirname "$FLUTTER")"
cp "$CANONICAL" "$FLUTTER"
echo "Synced home wizard choices to public www and the Flutter asset."
