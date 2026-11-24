#!/usr/bin/env bash
# Prepare a CDK diff or deploy for siutindei.
set -euo pipefail
mode="${1:-}"
case "$mode" in
  diff|deploy) ;;
  *) echo "::error::cdk-prepare.sh requires diff or deploy" >&2; exit 1 ;;
esac
if [ ! -f backend/infrastructure/package.json ]; then
  echo "run=false" >> "${GITHUB_OUTPUT:?}"
  exit 0
fi
if [ "$mode" = "deploy" ]; then
  python3 scripts/deploy/validate_search_area_scope.py
  (
    cd backend/infrastructure
    npm run build --if-present
  )
  {
    echo "run=true"
    echo "stacks=${CDK_STACKS:-}"
  } >> "${GITHUB_OUTPUT:?}"
  exit 0
fi
python3 - <<'PY'
import json
import os
from pathlib import Path

mapping = {
    "GoogleClientSecret": os.getenv("CDK_PARAM_GOOGLE_CLIENT_SECRET", ""),
    "ApplePrivateKey": os.getenv("CDK_PARAM_APPLE_PRIVATE_KEY", ""),
    "PublicApiKeyValue": os.getenv("CDK_PARAM_PUBLIC_API_KEY_VALUE", ""),
    "PublicWwwAttestationToken": os.getenv(
        "CDK_PARAM_PUBLIC_WWW_ATTESTATION_TOKEN", ""
    ),
    "PublicWwwAttestationTokenPrevious": os.getenv(
        "CDK_PARAM_PUBLIC_WWW_ATTESTATION_TOKEN_PREVIOUS", ""
    ),
    "PublicWwwOriginVerifySecret": os.getenv(
        "CDK_PARAM_PUBLIC_WWW_ORIGIN_VERIFY", ""
    ),
    "PublicWwwOriginVerifySecretPrevious": os.getenv(
        "CDK_PARAM_PUBLIC_WWW_ORIGIN_VERIFY_PREVIOUS", ""
    ),
    "AdminBootstrapTempPassword": os.getenv(
        "CDK_PARAM_ADMIN_BOOTSTRAP_TEMP_PASSWORD", ""
    ),
}
params = {k: v for k, v in mapping.items() if v}
if not params:
    raise SystemExit(0)

output_path = Path("/tmp/cdk-secret-params.json")
output_path.write_text(json.dumps(params), encoding="utf-8")
env_path = os.environ["GITHUB_ENV"]
with open(env_path, "a", encoding="utf-8") as handle:
    handle.write(f"CDK_SECRET_PARAM_FILE={output_path}\n")
PY

if [ -f /tmp/cdk-secret-params.json ]; then
  export CDK_SECRET_PARAM_FILE=/tmp/cdk-secret-params.json
fi
python3 - <<'PY'
import json
import os
from pathlib import Path

project_number = os.getenv("FIREBASE_MESSAGING_SENDER_ID", "").strip()
android_app_id = os.getenv("FIREBASE_ANDROID_APP_ID", "").strip()
ios_app_id = os.getenv("FIREBASE_IOS_APP_ID", "").strip()
apple_team_id = os.getenv("APPLE_TEAM_ID", "").strip()

params = {}

if apple_team_id:
    params["AppleTeamId"] = apple_team_id

if project_number and android_app_id and ios_app_id:
    audience = (
        f"projects/{project_number}/apps/{ios_app_id},"
        f"projects/{project_number}/apps/{android_app_id}"
    )
    params["DeviceAttestationAudience"] = audience

if not params:
    raise SystemExit(0)
output_path = Path("/tmp/cdk-non-secret-params.json")
output_path.write_text(json.dumps(params), encoding="utf-8")
env_path = os.environ["GITHUB_ENV"]
with open(env_path, "a", encoding="utf-8") as handle:
    handle.write(f"CDK_NON_SECRET_PARAM_FILE={output_path}\n")
PY

if [ -f /tmp/cdk-non-secret-params.json ]; then
  export CDK_NON_SECRET_PARAM_FILE=/tmp/cdk-non-secret-params.json
fi
cd backend/infrastructure
npm run build --if-present

# Empty means the all-stacks alias, which leaves the WAF stack out.
# The parameter list below needs concrete names. cdk-diff receives
# those names and the same committed plan as deploy. Parameters stay
# in the args file, so the plan is not asked for its extras.
CDK_STACKS="$(python3 - <<'PY'
import json
import os
from pathlib import Path

plan = json.loads(Path("cdk-plan.json").read_text(encoding="utf-8"))
raw = os.environ.get("CDK_STACKS", "").strip() or "all stacks"
aliases = plan.get("aliases") or {}
chosen = aliases[raw] if raw in aliases else raw.split()
print(" ".join(chosen))
PY
)"

PARAM_ARGS=()
PARAM_FILES=()

resolve_param_file() {
  local path="$1"
  if [ -z "$path" ]; then
    return 1
  fi
  if [ -f "$path" ]; then
    echo "$path"
    return 0
  fi
  if [ -n "${GITHUB_WORKSPACE:-}" ] && [ -f "$GITHUB_WORKSPACE/$path" ]; then
    echo "$GITHUB_WORKSPACE/$path"
    return 0
  fi
  return 1
}

if [ -n "${CDK_PARAM_FILE:-}" ]; then
  RESOLVED_PARAM_FILE=$(resolve_param_file "$CDK_PARAM_FILE" || true)
  if [ -z "$RESOLVED_PARAM_FILE" ]; then
    echo "::error::CDK_PARAM_FILE was not found"
    exit 1
  fi
  PARAM_FILES+=("$RESOLVED_PARAM_FILE")
fi
if [ -n "${CDK_SECRET_PARAM_FILE:-}" ] && [ -f "$CDK_SECRET_PARAM_FILE" ]; then
  PARAM_FILES+=("$CDK_SECRET_PARAM_FILE")
fi
if [ -n "${CDK_NON_SECRET_PARAM_FILE:-}" ] && [ -f "$CDK_NON_SECRET_PARAM_FILE" ]; then
  PARAM_FILES+=("$CDK_NON_SECRET_PARAM_FILE")
fi

if [ ${#PARAM_FILES[@]} -gt 0 ]; then
  PARAM_FILES_CSV=$(IFS=, ; echo "${PARAM_FILES[*]}")
  PARAM_ARGS_FILE="$(mktemp)"
  PARAM_FILES="$PARAM_FILES_CSV" STACKS="$CDK_STACKS" python3 - <<'PY' > "$PARAM_ARGS_FILE"
import json
import os
import sys

paths = [p for p in os.environ.get("PARAM_FILES", "").split(",") if p]
params = {}
for path in paths:
    with open(path, "r", encoding="utf-8") as handle:
        params.update(json.load(handle))

stack_set = set(os.environ.get("STACKS", "").split())
api_stack = "lxsoftware-siutindei"
admin_web_stack = "lxsoftware-siutindei-admin-web"
public_stack = "lxsoftware-siutindei-public-www"
admin_web_params = {"AdminWebDomainName", "AdminWebCertificateArn", "WafWebAclArn"}
public_params = {
    "PublicWwwDomainName",
    "PublicWwwCertificateArn",
    "PublicWwwStagingDomainName",
    "PublicWwwStagingCertificateArn",
    "WafWebAclArn",
    "SearchApiProxyOriginDomain",
}
# Authorizer (API stack) and CloudFront origin header (public stack).
origin_verify_param = "PublicWwwOriginVerifySecret"

def resolve_value(raw: str) -> str:
    """Replace <FROM_GITHUB_SECRET: X> / <FROM_GITHUB_VAR: X> placeholders."""
    raw = raw.strip()
    if raw.startswith("<FROM_GITHUB_SECRET:") and raw.endswith(">"):
        env_name = raw[len("<FROM_GITHUB_SECRET:") : -1].strip()
        return os.environ.get(env_name, "")
    if raw.startswith("<FROM_GITHUB_VAR:") and raw.endswith(">"):
        env_name = raw[len("<FROM_GITHUB_VAR:") : -1].strip()
        return os.environ.get(env_name, "")
    return raw

for key, value in params.items():
    value_str = ""
    if value is not None:
        value_str = resolve_value(str(value))
    value_str = value_str.replace("\r\n", "\n").replace("\r", "\n")
    value_str = value_str.replace("\n", "\\n").strip()
    if key != "WafWebAclArn" and not value_str:
        continue

    targets = []
    if key == origin_verify_param:
        targets.extend([api_stack, public_stack])
    if key in admin_web_params:
        if value_str or key != "WafWebAclArn":
            targets.append(admin_web_stack)
    if key in public_params:
        targets.append(public_stack)
    if not targets:
        targets.append(api_stack)

    for target in targets:
        if target not in stack_set:
            continue
        sys.stdout.buffer.write(b"--parameters\0")
        sys.stdout.buffer.write(
            f"{target}:{key}={value_str}".encode("utf-8") + b"\0"
        )
PY
  mapfile -d '' -t PARAM_ARGS < "$PARAM_ARGS_FILE"
fi

# bin/app.ts reads CDK_BOOTSTRAP_QUALIFIER. This command rejects
# the bootstrap-only qualifier flag.
IFS=$', \n\t' read -r -a STACK_LIST <<< "$CDK_STACKS"
STACK_ARGS=()
for stack in "${STACK_LIST[@]}"; do
  trimmed="${stack#"${stack%%[![:space:]]*}"}"
  trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
  if [ -n "$trimmed" ]; then
    STACK_ARGS+=("$trimmed")
  fi
done

if [ ${#PARAM_ARGS[@]} -gt 0 ]; then
  printf '%s\0' "${PARAM_ARGS[@]}" > "${RUNNER_TEMP:?}/cdk-args"
else
  : > "${RUNNER_TEMP:?}/cdk-args"
fi
{
  echo "run=true"
  echo "stacks=${STACK_ARGS[*]}"
} >> "$GITHUB_OUTPUT"

