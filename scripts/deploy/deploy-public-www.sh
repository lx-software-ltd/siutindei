#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# scripts/deploy/deploy-public-www.sh
#
# Deploys the static export under apps/public_www/out to one of the two
# environments managed by the lxsoftware-siutindei-public-www CloudFormation
# stack:
#
#   * staging    — full deploy + per-release marker + deny-all robots.txt
#   * production — full deploy *or* promote a previously deployed staging
#                  release (S3-only artifact copy)
#
# Promotion model:
#   * PUBLIC_WWW_PROMOTE_RELEASE_ID  = <id>     ← copy s3://staging/releases/<id>/
#                                                  to root of production bucket;
#                                                  pass PUBLIC_WWW_PROMOTION_BUILD_DIR
#                                                  to upload a fresh build with
#                                                  production env vars instead.
#   * PUBLIC_WWW_MAINTENANCE_MODE    = true     ← upload the branded coming-soon
#                                                  holding page from
#                                                  apps/public_www/maintenance/
#                                                  (HTML no-store; images 1h).
#
# /www/* CloudFront proxy switching is intentionally NOT implemented here. The
# scaffolded stack has no /www/* behavior. When the public API is added,
# port over the apply_www_proxy_mode logic from
# https://github.com/lcacchiani/evolvesprouts/blob/main/scripts/deploy/deploy-public-www.sh
# -----------------------------------------------------------------------------
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
APP_DIR="$ROOT_DIR/apps/public_www"
BUILD_DIR="$APP_DIR/out"
MAINTENANCE_DIR="$APP_DIR/maintenance"
STACK_NAME="${PUBLIC_WWW_STACK_NAME:-lxsoftware-siutindei-public-www}"
SOURCE_STACK_NAME="${PUBLIC_WWW_SOURCE_STACK_NAME:-$STACK_NAME}"
DEPLOY_ENVIRONMENT="${PUBLIC_WWW_ENVIRONMENT:-production}"
RELEASE_ID="${PUBLIC_WWW_RELEASE_ID:-}"
PROMOTE_RELEASE_ID="${PUBLIC_WWW_PROMOTE_RELEASE_ID:-}"
MAINTENANCE_MODE="${PUBLIC_WWW_MAINTENANCE_MODE:-false}"
ASSET_CACHE_CONTROL="public, max-age=31536000, immutable"
DOCUMENT_CACHE_CONTROL="public, max-age=300, must-revalidate"
NO_STORE_CACHE_CONTROL="no-store, max-age=0"
MAINTENANCE_ASSET_CACHE_CONTROL="public, max-age=3600, must-revalidate"
DEFAULT_LX_SOFTWARE_URL="https://www.lx-software.com"

if [ "$MAINTENANCE_MODE" != "true" ] && [ "$MAINTENANCE_MODE" != "false" ]; then
  echo "Unsupported PUBLIC_WWW_MAINTENANCE_MODE: '$MAINTENANCE_MODE'"
  echo "Allowed values: true, false"
  exit 1
fi

if [ -n "$PROMOTE_RELEASE_ID" ] && [ "$MAINTENANCE_MODE" = "true" ]; then
  echo "PUBLIC_WWW_PROMOTE_RELEASE_ID and PUBLIC_WWW_MAINTENANCE_MODE=true are mutually exclusive"
  exit 1
fi

if [ -n "$RELEASE_ID" ] && [ "$MAINTENANCE_MODE" = "true" ]; then
  echo "PUBLIC_WWW_RELEASE_ID cannot be used with PUBLIC_WWW_MAINTENANCE_MODE=true"
  exit 1
fi

require_stack_output() {
  local stack_name="$1"
  local output_key="$2"
  local query value

  query="Stacks[0].Outputs[?OutputKey=='$output_key'].OutputValue"
  value="$(aws cloudformation describe-stacks \
    --stack-name "$stack_name" \
    --query "$query" \
    --output text)"

  if [ -z "$value" ] || [ "$value" = "None" ]; then
    echo "Output '$output_key' not found for stack '$stack_name'"
    exit 1
  fi

  echo "$value"
}

get_environment_outputs() {
  local environment_name="$1"
  if [ "$environment_name" = "production" ]; then
    echo "PublicWwwBucketName PublicWwwDistributionId"
    return
  fi
  if [ "$environment_name" = "staging" ]; then
    echo "PublicWwwStagingBucketName PublicWwwStagingDistributionId"
    return
  fi
  echo "Unsupported PUBLIC_WWW_ENVIRONMENT: '$environment_name'"
  echo "Allowed values: production, staging"
  exit 1
}

validate_release_id() {
  local release_id="$1"
  if [[ ! "$release_id" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$ ]]; then
    echo "Invalid release ID: '$release_id'"
    echo "Allowed: letters, numbers, dot, dash, underscore (max 128 chars)."
    exit 1
  fi
}

validate_http_url_when_set() {
  local env_name="$1"
  local env_value="${2:-}"
  if [ -n "$env_value" ] && [[ ! "$env_value" =~ ^https?:// ]]; then
    echo "$env_name must start with http:// or https:// when set."
    exit 1
  fi
}

read_public_www_build_default() {
  local key="$1"
  python3 - "$APP_DIR/build-env.defaults.json" "$key" <<'PY'
import json
import sys
from pathlib import Path

defaults_path = Path(sys.argv[1])
key = sys.argv[2]
if not defaults_path.is_file():
    raise SystemExit(
        f"Public website build defaults not found: {defaults_path}"
    )
data = json.loads(defaults_path.read_text(encoding="utf-8"))
value = data.get(key, "")
if not isinstance(value, str) or not value.strip():
    raise SystemExit(
        f"Build default {key} must be a non-empty string in {defaults_path}"
    )
sys.stdout.write(value.strip())
PY
}

# Same public contacts as the full site. An exported NEXT_PUBLIC_* value
# wins; otherwise use build-env.defaults.json.
resolve_public_contact_value() {
  local env_name="$1"
  local default_key="$2"
  local env_value="${!env_name:-}"
  if [ -n "$env_value" ]; then
    printf '%s' "$env_value"
    return
  fi
  read_public_www_build_default "$default_key"
}

resolve_maintenance_email() {
  resolve_public_contact_value "NEXT_PUBLIC_EMAIL" "contactEmail"
}

resolve_maintenance_whatsapp_url() {
  resolve_public_contact_value "NEXT_PUBLIC_WHATSAPP_URL" "whatsappUrl"
}

validate_maintenance_contact_settings() {
  local email whatsapp_url
  email="$(resolve_maintenance_email)"
  whatsapp_url="$(resolve_maintenance_whatsapp_url)"
  if [[ ! "$email" =~ ^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$ ]]; then
    echo "contactEmail must be a valid email address."
    exit 1
  fi
  if [[ ! "$whatsapp_url" =~ ^https?:// ]]; then
    echo "whatsappUrl must start with http:// or https://."
    exit 1
  fi
  validate_http_url_when_set \
    "NEXT_PUBLIC_INSTAGRAM_URL" \
    "${NEXT_PUBLIC_INSTAGRAM_URL:-}"
  validate_http_url_when_set \
    "NEXT_PUBLIC_LX_SOFTWARE_URL" \
    "${NEXT_PUBLIC_LX_SOFTWARE_URL:-}"
  if [ -n "${NEXT_PUBLIC_BUILD_YEAR:-}" ] && \
    { [[ ! "$NEXT_PUBLIC_BUILD_YEAR" =~ ^[0-9]{4}$ ]] || \
      [ "$NEXT_PUBLIC_BUILD_YEAR" -lt 2000 ] || \
      [ "$NEXT_PUBLIC_BUILD_YEAR" -gt 2100 ]; }; then
    echo "NEXT_PUBLIC_BUILD_YEAR must be a year between 2000 and 2100."
    exit 1
  fi
}

resolve_maintenance_build_year() {
  if [ -n "${NEXT_PUBLIC_BUILD_YEAR:-}" ]; then
    printf '%s' "$NEXT_PUBLIC_BUILD_YEAR"
    return
  fi
  date +%Y
}

copy_required_maintenance_asset() {
  local source_path="$1"
  local destination_path="$2"
  if [ ! -f "$source_path" ]; then
    echo "Required maintenance asset not found: $source_path"
    exit 1
  fi
  mkdir -p "$(dirname "$destination_path")"
  cp "$source_path" "$destination_path"
}

inject_maintenance_partial() {
  local html_path="$1"
  local marker="$2"
  local snippet_path="$3"
  if [ ! -f "$snippet_path" ]; then
    echo "Maintenance partial not found: $snippet_path"
    exit 1
  fi
  python3 - "$html_path" "$marker" "$snippet_path" <<'PY'
from pathlib import Path
import sys

html_path = Path(sys.argv[1])
marker = sys.argv[2]
snippet_path = Path(sys.argv[3])
html = html_path.read_text(encoding="utf-8")
if marker not in html:
    raise SystemExit(f"Marker {marker} not found in {html_path}")
snippet = snippet_path.read_text(encoding="utf-8").rstrip("\n")
html_path.write_text(html.replace(marker, snippet), encoding="utf-8")
PY
}

assemble_maintenance_html() {
  local html_path="$1"
  inject_maintenance_partial \
    "$html_path" \
    "__MAINTENANCE_BUBBLES__" \
    "$MAINTENANCE_DIR/partials/bubbles.html"
  inject_maintenance_partial \
    "$html_path" \
    "__MAINTENANCE_FOOTER__" \
    "$MAINTENANCE_DIR/partials/footer.html"
}

escape_sed_replacement() {
  printf '%s' "$1" | sed -e 's/[\\&|]/\\&/g'
}

inject_maintenance_contact_values() {
  local html_path="$1"
  if [ ! -f "$html_path" ]; then
    echo "Maintenance HTML file not found: $html_path"
    exit 1
  fi
  local escaped_email escaped_whatsapp_url escaped_instagram_url
  local escaped_lx_software_url escaped_build_year
  escaped_email="$(escape_sed_replacement "$(resolve_maintenance_email)")"
  escaped_whatsapp_url="$(escape_sed_replacement \
    "$(resolve_maintenance_whatsapp_url)")"
  escaped_instagram_url="$(escape_sed_replacement "${NEXT_PUBLIC_INSTAGRAM_URL:-#}")"
  escaped_lx_software_url="$(escape_sed_replacement \
    "${NEXT_PUBLIC_LX_SOFTWARE_URL:-$DEFAULT_LX_SOFTWARE_URL}")"
  escaped_build_year="$(escape_sed_replacement "$(resolve_maintenance_build_year)")"
  sed -i \
    -e "s|__NEXT_PUBLIC_EMAIL__|$escaped_email|g" \
    -e "s|__NEXT_PUBLIC_WHATSAPP_URL__|$escaped_whatsapp_url|g" \
    -e "s|__NEXT_PUBLIC_INSTAGRAM_URL__|$escaped_instagram_url|g" \
    -e "s|__NEXT_PUBLIC_LX_SOFTWARE_URL__|$escaped_lx_software_url|g" \
    -e "s|__NEXT_PUBLIC_BUILD_YEAR__|$escaped_build_year|g" \
    "$html_path"
}

prepare_maintenance_build_dir() {
  validate_maintenance_contact_settings
  if [ ! -d "$MAINTENANCE_DIR" ]; then
    echo "Maintenance source not found at $MAINTENANCE_DIR"
    exit 1
  fi
  local maintenance_build_dir
  maintenance_build_dir="$(mktemp -d)"
  cp -a "$MAINTENANCE_DIR/." "$maintenance_build_dir/"
  if [ -f "$APP_DIR/public/favicon.ico" ]; then
    cp "$APP_DIR/public/favicon.ico" "$maintenance_build_dir/favicon.ico"
  fi
  if [ -f "$APP_DIR/public/favicon.svg" ]; then
    cp "$APP_DIR/public/favicon.svg" "$maintenance_build_dir/favicon.svg"
  fi
  copy_required_maintenance_asset \
    "$APP_DIR/public/images/brand/siutindei-logo-stacked.svg" \
    "$maintenance_build_dir/images/brand/siutindei-logo-stacked.svg"
  local bubble_name
  for bubble_name in \
    bubble-junk \
    bubble-tram \
    bubble-bao \
    bubble-clock-tower \
    bubble-bauhinia \
    bubble-lantern
  do
    copy_required_maintenance_asset \
      "$APP_DIR/public/images/small-world/${bubble_name}.webp" \
      "$maintenance_build_dir/images/small-world/${bubble_name}.webp"
  done
  assemble_maintenance_html "$maintenance_build_dir/index.html"
  if [ -f "$maintenance_build_dir/404.html" ]; then
    assemble_maintenance_html "$maintenance_build_dir/404.html"
  fi
  rm -rf "$maintenance_build_dir/partials"
  inject_maintenance_contact_values "$maintenance_build_dir/index.html"
  if [ -f "$maintenance_build_dir/404.html" ]; then
    inject_maintenance_contact_values "$maintenance_build_dir/404.html"
  fi
  if grep -R -q -E '__MAINTENANCE_|__NEXT_PUBLIC_' \
    "$maintenance_build_dir"/*.html; then
    echo "Unreplaced maintenance placeholders remain in the build dir."
    exit 1
  fi
  echo "$maintenance_build_dir"
}

assert_wildcard_invalidation_limit() {
  local max_wildcard_paths=15
  local wildcard_count=0
  local invalidation_path

  for invalidation_path in "$@"; do
    if [[ "$invalidation_path" == *"*"* ]]; then
      wildcard_count=$((wildcard_count + 1))
    fi
  done

  if [ "$wildcard_count" -gt "$max_wildcard_paths" ]; then
    echo "CloudFront allows at most $max_wildcard_paths wildcard invalidation paths in progress."
    echo "Configured invalidation request has $wildcard_count wildcard paths."
    return 1
  fi
}

invalidate_distribution() {
  local distribution_id="$1"
  local invalidation_scope="${2:-site}"
  if [ -z "$distribution_id" ] || [ "$distribution_id" = "None" ]; then
    return 0
  fi

  # Site-scope paths follow evolvesprouts: cover locale prefixes and
  # exported page prefixes so CloudFront drops rewritten cache keys such
  # as /en/index.html. /* is reserved for promote/maintenance.
  local -a invalidation_paths
  if [ "$invalidation_scope" = "full" ]; then
    invalidation_paths=("/*")
  else
    invalidation_paths=(
      "/"
      "/index.html"
      "/404.html"
      "/404/index.html"
      "/_not-found/index.html"
      "/_next/static/*"
      "/en*"
      "/zh-HK*"
      "/about*"
      "/search*"
      "/activity*"
      "/privacy*"
      "/terms*"
      "/fixtures/*"
      "/v1/activities/search*"
      "/robots.txt"
      "/sitemap.xml"
    )
  fi
  assert_wildcard_invalidation_limit "${invalidation_paths[@]}" || return 1

  local max_attempts=5
  local retry_delay_seconds=20
  local attempt=1
  local invalidation_output

  echo "Invalidating CloudFront distribution $distribution_id"
  while [ "$attempt" -le "$max_attempts" ]; do
    invalidation_output="$(mktemp)"
    if aws cloudfront create-invalidation \
      --distribution-id "$distribution_id" \
      --paths "${invalidation_paths[@]}" \
      >"$invalidation_output" 2>&1; then
      cat "$invalidation_output"
      rm -f "$invalidation_output"
      return 0
    fi

    local invalidation_error
    invalidation_error="$(<"$invalidation_output")"
    rm -f "$invalidation_output"

    if [[ "$invalidation_error" == *"TooManyInvalidationsInProgress"* ]] && \
      [ "$attempt" -lt "$max_attempts" ]; then
      echo "CloudFront invalidation queue is full (attempt $attempt/$max_attempts)."
      echo "Retrying in ${retry_delay_seconds}s..."
      sleep "$retry_delay_seconds"
      attempt=$((attempt + 1))
      continue
    fi

    echo "$invalidation_error"
    return 1
  done

  echo "CloudFront invalidation failed after $max_attempts attempts."
  return 1
}

sync_site_artifacts() {
  local source_dir="$1"
  local destination_uri="$2"
  if [ -d "$source_dir/_next/static" ]; then
    aws s3 sync \
      "$source_dir/_next/static" \
      "$destination_uri/_next/static" \
      --cache-control "$ASSET_CACHE_CONTROL"
  fi
  aws s3 sync \
    "$source_dir" \
    "$destination_uri" \
    --exclude "_next/static/*" \
    --exclude "releases/*" \
    --cache-control "$DOCUMENT_CACHE_CONTROL" \
    --delete
}

sync_release_artifacts() {
  local source_uri="$1"
  local destination_uri="$2"
  if aws s3 ls "$source_uri/_next/static/" >/dev/null 2>&1; then
    aws s3 sync \
      "$source_uri/_next/static" \
      "$destination_uri/_next/static" \
      --cache-control "$ASSET_CACHE_CONTROL"
  fi
  aws s3 sync \
    "$source_uri" \
    "$destination_uri" \
    --exclude "_next/static/*" \
    --exclude "releases/*" \
    --cache-control "$DOCUMENT_CACHE_CONTROL" \
    --delete
}

sync_maintenance_artifacts() {
  local source_dir="$1"
  local destination_uri="$2"
  if [ -d "$source_dir/images" ]; then
    aws s3 sync \
      "$source_dir/images" \
      "$destination_uri/images" \
      --cache-control "$MAINTENANCE_ASSET_CACHE_CONTROL" \
      --delete
  fi
  aws s3 sync \
    "$source_dir" \
    "$destination_uri" \
    --exclude "releases/*" \
    --exclude "images/*" \
    --cache-control "$NO_STORE_CACHE_CONTROL" \
    --delete
}

enforce_staging_robots_txt() {
  local bucket_name="$1"
  local robots_file
  robots_file="$(mktemp)"
  cat > "$robots_file" <<'EOF'
User-agent: *
Disallow: /
EOF
  aws s3 cp \
    "$robots_file" \
    "s3://$bucket_name/robots.txt" \
    --content-type "text/plain; charset=utf-8" \
    --cache-control "$NO_STORE_CACHE_CONTROL"
  rm -f "$robots_file"
}

# ------------------------- promotion path ------------------------------------

if [ -n "$PROMOTE_RELEASE_ID" ]; then
  validate_release_id "$PROMOTE_RELEASE_ID"

  SOURCE_BUCKET_NAME="$(require_stack_output \
    "$SOURCE_STACK_NAME" \
    "PublicWwwStagingBucketName")"
  TARGET_BUCKET_NAME="$(require_stack_output \
    "$STACK_NAME" \
    "PublicWwwBucketName")"
  TARGET_DISTRIBUTION_ID="$(require_stack_output \
    "$STACK_NAME" \
    "PublicWwwDistributionId")"

  KEY_COUNT="$(aws s3api list-objects-v2 \
    --bucket "$SOURCE_BUCKET_NAME" \
    --prefix "releases/$PROMOTE_RELEASE_ID/" \
    --max-keys 1 \
    --query "KeyCount" \
    --output text)"

  if [ "$KEY_COUNT" = "0" ]; then
    echo "Release '$PROMOTE_RELEASE_ID' not found in source stack"
    echo "Expected prefix: s3://$SOURCE_BUCKET_NAME/releases/$PROMOTE_RELEASE_ID/"
    exit 1
  fi

  if [ -n "${PUBLIC_WWW_PROMOTION_BUILD_DIR:-}" ]; then
    PROMOTION_BUILD_DIR="${PUBLIC_WWW_PROMOTION_BUILD_DIR}"
    if [ ! -d "$PROMOTION_BUILD_DIR" ]; then
      echo "Promotion build directory not found: $PROMOTION_BUILD_DIR"
      exit 1
    fi
    BUILD_DIR="$PROMOTION_BUILD_DIR"
    echo "Promoting release '$PROMOTE_RELEASE_ID' to production using local build output"
    echo "Syncing Public WWW to s3://$TARGET_BUCKET_NAME"
    sync_site_artifacts "$BUILD_DIR" "s3://$TARGET_BUCKET_NAME"
  else
    echo "Promoting release '$PROMOTE_RELEASE_ID' from staging to production (S3 artifact copy)"
    sync_release_artifacts \
      "s3://$SOURCE_BUCKET_NAME/releases/$PROMOTE_RELEASE_ID" \
      "s3://$TARGET_BUCKET_NAME"
  fi

  invalidate_distribution "$TARGET_DISTRIBUTION_ID" "full"
  exit 0
fi

# ------------------------- normal / maintenance path -------------------------

read -r TARGET_BUCKET_OUTPUT_KEY TARGET_DISTRIBUTION_OUTPUT_KEY <<< \
  "$(get_environment_outputs "$DEPLOY_ENVIRONMENT")"
TARGET_BUCKET_NAME="$(require_stack_output \
  "$STACK_NAME" \
  "$TARGET_BUCKET_OUTPUT_KEY")"
TARGET_DISTRIBUTION_ID="$(require_stack_output \
  "$STACK_NAME" \
  "$TARGET_DISTRIBUTION_OUTPUT_KEY")"

if [ "$MAINTENANCE_MODE" = "true" ]; then
  MAINTENANCE_BUILD_DIR="$(prepare_maintenance_build_dir)"
  echo "Syncing maintenance website to s3://$TARGET_BUCKET_NAME"
  sync_maintenance_artifacts "$MAINTENANCE_BUILD_DIR" "s3://$TARGET_BUCKET_NAME"
  rm -rf "$MAINTENANCE_BUILD_DIR"

  if [ "$DEPLOY_ENVIRONMENT" = "staging" ]; then
    echo "Applying staging robots.txt deny-all policy"
    enforce_staging_robots_txt "$TARGET_BUCKET_NAME"
  fi

  invalidate_distribution "$TARGET_DISTRIBUTION_ID" "full"
  exit 0
fi

if [ ! -d "$BUILD_DIR" ]; then
  echo "Build output not found at $BUILD_DIR"
  echo "Run: (cd apps/public_www && npm run build)"
  exit 1
fi

echo "Syncing Public WWW to s3://$TARGET_BUCKET_NAME"
sync_site_artifacts "$BUILD_DIR" "s3://$TARGET_BUCKET_NAME"

if [ -n "$RELEASE_ID" ]; then
  validate_release_id "$RELEASE_ID"
  echo "Saving immutable release at releases/$RELEASE_ID/"
  sync_site_artifacts "$BUILD_DIR" "s3://$TARGET_BUCKET_NAME/releases/$RELEASE_ID"

  if [ "$DEPLOY_ENVIRONMENT" = "staging" ]; then
    echo "Updating staging latest release marker: $RELEASE_ID"
    MARKER_FILE="$(mktemp)"
    printf "%s\n" "$RELEASE_ID" > "$MARKER_FILE"
    aws s3 cp \
      "$MARKER_FILE" \
      "s3://$TARGET_BUCKET_NAME/releases/latest-release-id.txt" \
      --content-type "text/plain; charset=utf-8" \
      --cache-control "$NO_STORE_CACHE_CONTROL"
    rm -f "$MARKER_FILE"
  fi
fi

if [ "$DEPLOY_ENVIRONMENT" = "staging" ]; then
  echo "Applying staging robots.txt deny-all policy"
  enforce_staging_robots_txt "$TARGET_BUCKET_NAME"
fi

invalidate_distribution "$TARGET_DISTRIBUTION_ID"
