#!/usr/bin/env bash
# Resolve the release id for a public website promotion.
set -euo pipefail
if [ "${1:-}" = "bucket-read" ]; then
  mode="${PROMOTION_MODE:-}"
  if [ "$mode" != "maintenance_on" ]; then
    echo "read_staging_bucket=true" >> "${GITHUB_OUTPUT:?}"
  else
    echo "read_staging_bucket=false" >> "${GITHUB_OUTPUT:?}"
  fi
  exit 0
fi
if [ "${GITHUB_EVENT_NAME:-}" = "schedule" ]; then
  RESOLVED_PROMOTION_MODE="refresh_production"
else
  RESOLVED_PROMOTION_MODE="${PROMOTION_MODE:-latest_staging}"
fi

if [ "$RESOLVED_PROMOTION_MODE" = "maintenance_on" ]; then
  echo "release_id=" >> "$GITHUB_OUTPUT"
  echo "maintenance_mode=true" >> "$GITHUB_OUTPUT"
  echo "promotion_mode=$RESOLVED_PROMOTION_MODE" >> "$GITHUB_OUTPUT"
  echo "deploy=false" >> "$GITHUB_OUTPUT"
  echo "skip=false" >> "$GITHUB_OUTPUT"
  echo "build_sha=" >> "$GITHUB_OUTPUT"
  exit 0
fi

# Release artifacts and the production markers live in the staging bucket.
STAGING_BUCKET="$(python3 -c 'import json,os; print(json.loads(os.environ["STACK_JSON"])["PublicWwwStagingBucketName"])')"
if [ -z "$STAGING_BUCKET" ]; then
  echo 'Staging bucket output not found on Public Website stack'
  exit 1
fi
# Step output only. A job output would be dropped because the name
# contains the account id.
echo "staging_bucket=$STAGING_BUCKET" >> "$GITHUB_OUTPUT"

if [ "$RESOLVED_PROMOTION_MODE" = "release_id" ]; then
  if [ -z "${INPUT_RELEASE_ID:-}" ]; then
    echo 'release_id is required when promotion_mode=release_id'
    exit 1
  fi
  SELECTED_RELEASE_ID="$INPUT_RELEASE_ID"
elif [ "$RESOLVED_PROMOTION_MODE" = "refresh_production" ]; then
  RELEASE_MARKER="$(mktemp)"
  BUILD_MARKER="$(mktemp)"
  if ! aws s3 cp --only-show-errors "s3://$STAGING_BUCKET/releases/production-release-id.txt" "$RELEASE_MARKER" \
    || ! aws s3 cp --only-show-errors "s3://$STAGING_BUCKET/releases/production-build-sha.txt" "$BUILD_MARKER"; then
    echo '::notice::No production build is recorded yet. Promote a release once to start daily refreshes.'
    echo "skip=true" >> "$GITHUB_OUTPUT"
    echo "deploy=false" >> "$GITHUB_OUTPUT"
    echo "build_sha=" >> "$GITHUB_OUTPUT"
    echo "maintenance_mode=false" >> "$GITHUB_OUTPUT"
    echo "promotion_mode=$RESOLVED_PROMOTION_MODE" >> "$GITHUB_OUTPUT"
    exit 0
  fi
  SELECTED_RELEASE_ID="$(tr -d '\r\n' < "$RELEASE_MARKER")"
  BUILD_SHA="$(tr -d '\r\n' < "$BUILD_MARKER")"
  rm -f "$RELEASE_MARKER" "$BUILD_MARKER"
  if ! printf '%s' "$BUILD_SHA" | grep -Eq '^[0-9a-f]{40}$'; then
    echo "Production build marker is not a commit SHA: '$BUILD_SHA'"
    exit 1
  fi
  echo "build_sha=$BUILD_SHA" >> "$GITHUB_OUTPUT"
elif [ "$RESOLVED_PROMOTION_MODE" = "latest_staging" ]; then
  MARKER_FILE="$(mktemp)"
  aws s3 cp \
    "s3://$STAGING_BUCKET/releases/latest-release-id.txt" \
    "$MARKER_FILE"
  SELECTED_RELEASE_ID="$(tr -d '\r\n' < "$MARKER_FILE")"
  rm -f "$MARKER_FILE"
  if [ -z "$SELECTED_RELEASE_ID" ]; then
    echo 'Latest staging release marker is empty'
    exit 1
  fi
else
  echo "Unsupported promotion_mode: $RESOLVED_PROMOTION_MODE"
  exit 1
fi

if [ -z "$SELECTED_RELEASE_ID" ]; then
  echo 'Resolved release ID is empty'
  exit 1
fi
echo "release_id=$SELECTED_RELEASE_ID" >> "$GITHUB_OUTPUT"
echo "maintenance_mode=false" >> "$GITHUB_OUTPUT"
echo "promotion_mode=$RESOLVED_PROMOTION_MODE" >> "$GITHUB_OUTPUT"
echo "deploy=true" >> "$GITHUB_OUTPUT"
echo "skip=false" >> "$GITHUB_OUTPUT"
if [ "$RESOLVED_PROMOTION_MODE" != "refresh_production" ]; then
  echo "build_sha=" >> "$GITHUB_OUTPUT"
fi
