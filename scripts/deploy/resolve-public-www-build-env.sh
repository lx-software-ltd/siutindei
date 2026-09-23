#!/usr/bin/env bash
# Writes public website build env defaults to GITHUB_OUTPUT.
# Domains come from CDK params; branding from apps/public_www/build-env.defaults.json.
# GitHub Environment vars may override these values in workflow env blocks.
set -euo pipefail

CDK_PARAMS_FILE="${1:-backend/infrastructure/params/production.json}"
BUILD_DEFAULTS_FILE="${2:-apps/public_www/build-env.defaults.json}"

if [ -z "${GITHUB_OUTPUT:-}" ]; then
  echo 'GITHUB_OUTPUT is not set'
  exit 1
fi

python3 - "$CDK_PARAMS_FILE" "$BUILD_DEFAULTS_FILE" <<'PY'
import json
import os
import sys
from pathlib import Path

cdk_params_path = Path(sys.argv[1])
build_defaults_path = Path(sys.argv[2])

cdk_params = json.loads(cdk_params_path.read_text(encoding="utf-8"))
build_defaults = json.loads(build_defaults_path.read_text(encoding="utf-8"))


def cdk_get(key: str, default: str = "") -> str:
    return str(cdk_params.get(key, default)).strip()


def build_get(key: str, default: str = "") -> str:
    return str(build_defaults.get(key, default)).strip()


prod_domain = cdk_get("PublicWwwDomainName")
staging_domain = cdk_get("PublicWwwStagingDomainName")
if not prod_domain or not staging_domain:
    raise SystemExit(
        "PublicWwwDomainName and PublicWwwStagingDomainName are required "
        f"in {cdk_params_path}"
    )

contact_email = build_get("contactEmail")
if not contact_email:
    contact_email = cdk_get("AuthEmailFromAddress")

outputs = {
    "production_site_origin": f"https://{prod_domain}",
    "staging_site_origin": f"https://{staging_domain}",
    "site_name": build_get("siteName", "Siu Tin Dei"),
    "site_tagline": build_get(
        "siteTagline",
        "Curated children's activities in Hong Kong.",
    ),
    "contact_email": contact_email,
    "whatsapp_url": build_get("whatsappUrl"),
    "whatsapp_display": build_get("whatsappDisplay"),
}

out_path = os.environ["GITHUB_OUTPUT"]
with open(out_path, "a", encoding="utf-8") as handle:
    for key, value in outputs.items():
        handle.write(f"{key}={value}\n")
PY
