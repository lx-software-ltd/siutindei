#!/usr/bin/env bash
set -euo pipefail
python3 scripts/check_openapi_routes.py
python3 scripts/check_stack_invariants.py
node scripts/check-lambda-docs.mjs
npm ci --prefix apps/admin_web
npm run generate:api --prefix apps/admin_web
git diff --exit-code apps/admin_web/src/types/api-admin.generated.ts
