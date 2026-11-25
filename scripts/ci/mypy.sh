#!/usr/bin/env bash
set -euo pipefail
python3 -m pip install -q 'mypy==1.8.0'
# mypy pending: mypy 1.8.0 does not pass these directories.
# backend/src crashes on its module layout.
# backend/lambda/auth: duplicate module named "handler"
# backend/lambda/authorizers: duplicate module named "handler"
# backend/lambda/category_suggestions: 8 errors
# backend/lambda/manager_request_processor: 8 errors
# backend/lambda/migrations: source file found twice under different module names
dirs=(
  backend/lambda/admin
  backend/lambda/admin_bootstrap
  backend/lambda/api_key_rotation
  backend/lambda/aws_proxy
  backend/lambda/catalogue_snapshot
  backend/lambda/health
  backend/lambda/listing_events_ingest
  backend/lambda/listing_events_rollup
  backend/lambda/search
)
for dir in "${dirs[@]}"; do
  echo "mypy $dir"
  (
    cd "$dir"
    python3 -m mypy --ignore-missing-imports .
  )
done
