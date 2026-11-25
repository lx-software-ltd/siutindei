#!/usr/bin/env bash
# Public website checks. pre-build runs the wizard, scope, and env contract.
set -euo pipefail
phase="${1:?pre-build or post-build}"
case "$phase" in
  pre-build)
    bash scripts/codegen/sync-home-wizard-choices.sh --check
    python3 scripts/deploy/validate_search_area_scope.py
    npm run assert:build-env-contract --prefix apps/public_www
    ;;
  post-build)
    ;;
  *)
    echo "public-www-checks.sh expects pre-build or post-build" >&2
    exit 1
    ;;
esac
