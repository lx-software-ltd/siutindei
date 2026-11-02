"""Amplify configuration built for the mobile release workflows."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "deploy"
    / "build_amplify_config.py"
)


def _module():
    spec = importlib.util.spec_from_file_location("build_amplify_config", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


OUTPUTS = {
    "ApiUrl": "https://abc123.execute-api.ap-southeast-1.amazonaws.com/prod/",
    "ApiCustomDomainUrl": "https://api.example.test",
    "UserPoolId": "ap-southeast-1_Example1",
    "UserPoolClientId": "exampleclientid",
}

PARAMS = {
    "CognitoDomainPrefix": "example-prefix",
    "CognitoCustomDomainName": "auth.example.test",
    "CognitoCallbackUrls": (
        "com.lxsoftware.siutindei://callback,https://example.test/auth/callback"
    ),
    "CognitoLogoutUrls": "com.lxsoftware.siutindei://logout,https://example.test/",
}


def test_config_uses_custom_domains_and_mobile_redirects() -> None:
    config = _module().build_config(OUTPUTS, PARAMS, "ap-southeast-1")

    api = config["api"]["plugins"]["awsAPIPlugin"]["activitiesApi"]
    assert api == {
        "endpointType": "REST",
        "endpoint": "https://api.example.test",
        "region": "ap-southeast-1",
        "authorizationType": "NONE",
    }
    cognito = config["auth"]["plugins"]["awsCognitoAuthPlugin"]
    assert cognito["CognitoUserPool"]["Default"] == {
        "PoolId": "ap-southeast-1_Example1",
        "AppClientId": "exampleclientid",
        "Region": "ap-southeast-1",
    }
    auth = cognito["Auth"]["Default"]
    assert auth["authenticationFlowType"] == "CUSTOM_AUTH"
    assert auth["OAuth"] == {
        "WebDomain": "auth.example.test",
        "AppClientId": "exampleclientid",
        "SignInRedirectURI": "com.lxsoftware.siutindei://callback",
        "SignOutRedirectURI": "com.lxsoftware.siutindei://logout",
        "Scopes": ["openid", "email", "profile"],
    }


def test_config_falls_back_to_stage_url_and_cognito_prefix_domain() -> None:
    outputs = {
        key: value for key, value in OUTPUTS.items() if key != "ApiCustomDomainUrl"
    }
    params = {**PARAMS, "CognitoCustomDomainName": ""}

    config = _module().build_config(outputs, params, "ap-southeast-1")

    api = config["api"]["plugins"]["awsAPIPlugin"]["activitiesApi"]
    assert api["endpoint"] == (
        "https://abc123.execute-api.ap-southeast-1.amazonaws.com/prod"
    )
    oauth = config["auth"]["plugins"]["awsCognitoAuthPlugin"]["Auth"]["Default"][
        "OAuth"
    ]
    assert oauth["WebDomain"] == "example-prefix.auth.ap-southeast-1.amazoncognito.com"


@pytest.mark.parametrize("missing", ["UserPoolId", "UserPoolClientId", "ApiUrl"])
def test_missing_stack_output_is_an_error(missing: str) -> None:
    outputs = {
        key: value
        for key, value in OUTPUTS.items()
        if key not in {missing, "ApiCustomDomainUrl"}
    }
    with pytest.raises(SystemExit, match=missing):
        _module().build_config(outputs, PARAMS, "ap-southeast-1")


def test_mobile_redirect_is_required() -> None:
    params = {**PARAMS, "CognitoCallbackUrls": "https://example.test/auth/callback"}
    with pytest.raises(SystemExit, match="CognitoCallbackUrls"):
        _module().build_config(OUTPUTS, params, "ap-southeast-1")


def test_write_defines_file_holds_config_as_a_string(tmp_path: Path) -> None:
    module = _module()
    config = module.build_config(OUTPUTS, PARAMS, "ap-southeast-1")
    target = tmp_path / "defines.json"

    module.write_defines(config, target)

    defines = json.loads(target.read_text())
    assert list(defines) == ["AMPLIFY_CONFIG"]
    assert json.loads(defines["AMPLIFY_CONFIG"]) == config
