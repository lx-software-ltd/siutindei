#!/usr/bin/env python3
"""Write the mobile app's AMPLIFY_CONFIG as a `--dart-define-from-file` JSON.

Reads the API stack outputs (`aws cloudformation describe-stacks`) and the
CDK parameter file, so the release build uses the deployed API, user pool,
and Hosted UI domain. The API key stays a separate `--dart-define`.

Usage:
    build_amplify_config.py --stack lxsoftware-siutindei \
        --params backend/infrastructure/params/production.json \
        --region ap-southeast-1 --output build/amplify-defines.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

API_NAME = "activitiesApi"
MOBILE_SCHEME = "com.lxsoftware.siutindei://"
OAUTH_SCOPES = ["openid", "email", "profile"]


def _require(values: dict[str, str], key: str, source: str) -> str:
    value = (values.get(key) or "").strip()
    if not value:
        raise SystemExit(f"{source} is missing {key}")
    return value


def _mobile_uri(params: dict[str, str], key: str) -> str:
    for uri in (params.get(key) or "").split(","):
        if uri.strip().startswith(MOBILE_SCHEME):
            return uri.strip()
    raise SystemExit(f"{key} has no {MOBILE_SCHEME} URI")


def build_config(
    outputs: dict[str, str],
    params: dict[str, str],
    region: str,
) -> dict[str, Any]:
    """Return the Amplify Gen 1 configuration for the deployed stack."""
    endpoint = (
        (outputs.get("ApiSecondaryCustomDomainUrl") or "").strip()
        or (outputs.get("ApiCustomDomainUrl") or "").strip()
        or _require(outputs, "ApiUrl", "stack outputs")
    )
    pool_id = _require(outputs, "UserPoolId", "stack outputs")
    client_id = _require(outputs, "UserPoolClientId", "stack outputs")
    web_domain = (params.get("CognitoCustomDomainName") or "").strip() or (
        f"{_require(params, 'CognitoDomainPrefix', 'CDK parameters')}"
        f".auth.{region}.amazoncognito.com"
    )
    return {
        "UserAgent": "aws-amplify-cli/2.0",
        "Version": "1.0",
        "api": {
            "plugins": {
                "awsAPIPlugin": {
                    API_NAME: {
                        "endpointType": "REST",
                        "endpoint": endpoint.rstrip("/"),
                        "region": region,
                        "authorizationType": "NONE",
                    }
                }
            }
        },
        "auth": {
            "plugins": {
                "awsCognitoAuthPlugin": {
                    "UserAgent": "aws-amplify-cli/0.1.0",
                    "Version": "0.1.0",
                    "CognitoUserPool": {
                        "Default": {
                            "PoolId": pool_id,
                            "AppClientId": client_id,
                            "Region": region,
                        }
                    },
                    "Auth": {
                        "Default": {
                            "authenticationFlowType": "CUSTOM_AUTH",
                            "OAuth": {
                                "WebDomain": web_domain,
                                "AppClientId": client_id,
                                "SignInRedirectURI": _mobile_uri(
                                    params, "CognitoCallbackUrls"
                                ),
                                "SignOutRedirectURI": _mobile_uri(
                                    params, "CognitoLogoutUrls"
                                ),
                                "Scopes": list(OAUTH_SCOPES),
                            },
                        }
                    },
                }
            }
        },
    }


def write_defines(config: dict[str, Any], target: Path) -> None:
    """Write `{"AMPLIFY_CONFIG": "<json>"}` for `--dart-define-from-file`."""
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {"AMPLIFY_CONFIG": json.dumps(config, separators=(",", ":"))}
    target.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _stack_outputs(stack: str, region: str) -> dict[str, str]:
    raw = subprocess.run(
        [
            "aws",
            "cloudformation",
            "describe-stacks",
            "--stack-name",
            stack,
            "--region",
            region,
            "--query",
            "Stacks[0].Outputs",
            "--output",
            "json",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return {item["OutputKey"]: item["OutputValue"] for item in json.loads(raw) or []}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stack", default="lxsoftware-siutindei")
    parser.add_argument("--params", required=True, type=Path)
    parser.add_argument("--region", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    params = json.loads(args.params.read_text(encoding="utf-8"))
    config = build_config(_stack_outputs(args.stack, args.region), params, args.region)
    write_defines(config, args.output)


if __name__ == "__main__":
    main()
