#!/usr/bin/env bash
# Download the public catalogue snapshot that CatalogueSnapshotFunction
# writes, for the public website build to pre-render activity pages.
#
# Env:
#   API_STACK_NAME        stack that exports the bucket (default lxsoftware-siutindei)
#   SNAPSHOT_OUTPUT_PATH  where to write the file (required)
#   SNAPSHOT_KEY          object key (default public-www/catalogue-snapshot.json)
#
# Writes `path=<file>` to $GITHUB_OUTPUT when it is set.
set -euo pipefail

API_STACK_NAME="${API_STACK_NAME:-lxsoftware-siutindei}"
SNAPSHOT_KEY="${SNAPSHOT_KEY:-public-www/catalogue-snapshot.json}"
: "${SNAPSHOT_OUTPUT_PATH:?SNAPSHOT_OUTPUT_PATH is required}"

bucket="$(aws cloudformation describe-stacks \
  --stack-name "$API_STACK_NAME" \
  --query "Stacks[0].Outputs[?OutputKey=='PublicWwwCatalogueSnapshotBucketName'].OutputValue" \
  --output text)"
if [ -z "$bucket" ] || [ "$bucket" = "None" ]; then
  echo "PublicWwwCatalogueSnapshotBucketName output not found on $API_STACK_NAME" >&2
  exit 1
fi

mkdir -p "$(dirname "$SNAPSHOT_OUTPUT_PATH")"
aws s3 cp --only-show-errors "s3://$bucket/$SNAPSHOT_KEY" "$SNAPSHOT_OUTPUT_PATH"

SNAPSHOT_OUTPUT_PATH="$SNAPSHOT_OUTPUT_PATH" \
python3 - <<'PY'
import json
import os
import sys

path = os.environ["SNAPSHOT_OUTPUT_PATH"]
with open(path, encoding="utf-8") as handle:
    snapshot = json.load(handle)
if snapshot.get("schema_version") != 1:
    sys.exit(f"Unsupported catalogue snapshot schema: {snapshot.get('schema_version')!r}")
items = snapshot.get("items")
if not isinstance(items, list) or not items:
    sys.exit("Catalogue snapshot has no items")
activities = {item["activity"]["id"] for item in items}
print(f"Catalogue snapshot: {len(items)} rows, {len(activities)} activities, generated {snapshot.get('generated_at')}")
PY

if [ -n "${GITHUB_OUTPUT:-}" ]; then
  echo "path=$SNAPSHOT_OUTPUT_PATH" >> "$GITHUB_OUTPUT"
fi
