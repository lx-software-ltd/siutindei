"""Tests for the Cloudflare edge policy plan/apply tool."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "scripts" / "cloudflare" / "edge_policy.py"
_POLICY = _ROOT / "scripts" / "cloudflare" / "public_www_edge_policy.json"
_SECRET = "unit-test-edge-secret-0123456789abcdefghij"


def _load_module():
    spec = importlib.util.spec_from_file_location("edge_policy", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Dataclasses resolve string annotations through sys.modules.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


edge_policy = _load_module()


class FakeCloudflare:
    """Serves canned GET responses and records every write."""

    def __init__(self, responses: dict[str, Any]):
        self.responses = responses
        self.writes: list[tuple[str, str, dict[str, Any] | None]] = []

    def __call__(
        self, method: str, path: str, body: dict[str, Any] | None
    ) -> dict[str, Any]:
        if method != "GET":
            self.writes.append((method, path, body))
            return {"success": True, "result": body}
        key = path.split("?")[0]
        response = self.responses.get(key)
        if response is None:
            raise edge_policy.ApiError(404, ["not found"])
        if isinstance(response, edge_policy.ApiError):
            raise response
        return {"success": True, "result": response}


def _policy(env: dict[str, str] | None = None, **overrides):
    return edge_policy.load_policy(_POLICY, env or {}, **overrides)


def _api(responses: dict[str, Any]) -> tuple[Any, FakeCloudflare]:
    fake = FakeCloudflare(responses)
    return edge_policy.CloudflareApi("token", requester=fake), fake


def _live_state(policy, *, proxied: bool, extra_rule_fields: bool = True):
    """Zone state that already matches the policy except for DNS."""
    state: dict[str, Any] = {
        "/zones/z1/bot_management": {**policy.bot_management, "enable_js": False},
        "/zones/z1/dns_records": [
            {
                "id": "rec1",
                "name": policy.hostname,
                "type": "CNAME",
                "content": "d123.cloudfront.net",
                "proxied": proxied,
                "proxiable": True,
            }
        ],
    }
    for setting, value in policy.settings.items():
        state[f"/zones/z1/settings/{setting}"] = {"id": setting, "value": value}
    for phase, spec in policy.rulesets.items():
        rules = []
        for index, rule in enumerate(spec["rules"]):
            copy = dict(rule)
            if extra_rule_fields:
                copy.update({"id": f"r{index}", "version": "3", "ref": f"r{index}"})
            rules.append(copy)
        state[f"/zones/z1/rulesets/phases/{phase}/entrypoint"] = {"rules": rules}
    return state


def test_policy_resolves_hostname_and_secret_placeholders():
    policy = _policy({"PUBLIC_WWW_EDGE_VERIFY_SECRET": _SECRET})
    assert policy.hostname == "siutindei.com"
    assert policy.dns["name"] == "siutindei.com"
    transform = policy.rulesets["http_request_late_transform"]["rules"][0]
    header = transform["action_parameters"]["headers"]["x-proxy-verify"]
    assert header["value"] == _SECRET
    assert policy.secrets == (_SECRET,)
    assert policy.missing == {}
    assert "${" not in json.dumps(policy.rulesets)


def test_policy_reports_missing_secret_for_the_transform_phase_only():
    policy = _policy({})
    assert policy.missing == {
        "rulesets:http_request_late_transform": ["PUBLIC_WWW_EDGE_VERIFY_SECRET"]
    }
    assert policy.secrets == ()


def test_policy_overrides_hostname_zone_and_proxied():
    policy = _policy(
        {}, zone_name="lx-software.com", hostname="staging.example", proxied=False
    )
    assert policy.zone_name == "lx-software.com"
    assert policy.dns == {"name": "staging.example", "type": "CNAME", "proxied": False}
    cache_rule = policy.rulesets["http_request_cache_settings"]["rules"][0]
    assert 'http.host eq "staging.example"' in cache_rule["expression"]


def test_policy_uses_only_free_plan_rate_limit_parameters():
    policy = _policy({})
    rules = policy.rulesets["http_ratelimit"]["rules"]
    assert len(rules) == 1
    ratelimit = rules[0]["ratelimit"]
    assert ratelimit["period"] == 10
    assert ratelimit["mitigation_timeout"] == 10
    assert "cf.colo.id" in ratelimit["characteristics"]
    assert rules[0]["action"] == "block"
    custom = policy.rulesets["http_request_firewall_custom"]["rules"]
    assert len(custom) <= 5
    assert all(rule["action"] == "block" for rule in custom)


def test_search_rules_never_touch_html_navigations():
    policy = _policy({})
    for phase in ("http_ratelimit", "http_request_firewall_custom"):
        for rule in policy.rulesets[phase]["rules"]:
            assert (
                'http.request.uri.path eq "/v1/activities/search"'
                in (rule["expression"])
            )


def test_is_subset_ignores_extra_keys_in_current_state():
    assert edge_policy.is_subset(
        {"a": 1, "b": {"c": [1, 2]}}, {"a": 1, "b": {"c": [1, 2], "d": 0}, "e": 5}
    )
    assert not edge_policy.is_subset({"a": 1}, {"a": 2})
    assert not edge_policy.is_subset({"a": [1]}, {"a": [1, 2]})
    assert not edge_policy.is_subset({"a": {"b": 1}}, {"a": None})


def test_plan_is_noop_when_live_state_matches_policy():
    policy = _policy({"PUBLIC_WWW_EDGE_VERIFY_SECRET": _SECRET})
    api, fake = _api(_live_state(policy, proxied=True))
    changes = edge_policy.build_plan(api, "z1", policy, edge_policy.SECTIONS)
    assert {change.kind for change in changes} == {"noop"}
    assert fake.writes == []


def test_plan_reports_updates_creates_blocked_and_unreadable():
    policy = _policy({})
    api, _ = _api(
        {
            "/zones/z1/settings/ssl": {"id": "ssl", "value": "full"},
            "/zones/z1/settings/email_obfuscation": {"value": "off"},
            "/zones/z1/settings/browser_cache_ttl": {"value": 0},
            "/zones/z1/settings/rocket_loader": {"value": "off"},
            "/zones/z1/settings/always_use_https": {"value": "on"},
            "/zones/z1/settings/browser_check": {"value": "on"},
            "/zones/z1/rulesets/phases/http_request_cache_settings/entrypoint": (
                edge_policy.ApiError(403, ["request is not authorized"])
            ),
            "/zones/z1/bot_management": {
                "fight_mode": True,
                "ai_bots_protection": "disabled",
            },
            "/zones/z1/dns_records": [
                {
                    "id": "rec1",
                    "name": "siutindei.com",
                    "proxied": False,
                    "proxiable": True,
                    "content": "d1.cloudfront.net",
                }
            ],
        }
    )
    changes = edge_policy.build_plan(api, "z1", policy, edge_policy.SECTIONS)
    by_target = {(c.section, c.target): c for c in changes}
    assert by_target[("settings", "ssl")].kind == "update"
    assert by_target[("settings", "ssl")].detail == '"full" -> "strict"'
    assert by_target[("settings", "browser_check")].kind == "noop"
    assert by_target[("rulesets", "http_request_cache_settings")].kind == "unreadable"
    assert by_target[("rulesets", "http_request_late_transform")].kind == "blocked"
    assert by_target[("rulesets", "http_request_firewall_custom")].kind == "create"
    assert by_target[("rulesets", "http_ratelimit")].kind == "create"
    assert by_target[("bot", "bot_management")].kind == "update"
    assert by_target[("dns", "siutindei.com")].kind == "update"
    assert "proxied false -> true" in by_target[("dns", "siutindei.com")].detail


def test_apply_writes_in_section_order_with_expected_payloads():
    policy = _policy({"PUBLIC_WWW_EDGE_VERIFY_SECRET": _SECRET})
    live = _live_state(policy, proxied=False)
    live["/zones/z1/settings/ssl"] = {"value": "full"}
    del live["/zones/z1/rulesets/phases/http_ratelimit/entrypoint"]
    live["/zones/z1/bot_management"] = {
        "fight_mode": False,
        "ai_bots_protection": "disabled",
    }
    api, fake = _api(live)
    changes = edge_policy.build_plan(api, "z1", policy, edge_policy.SECTIONS)
    applied = edge_policy.apply_plan(api, changes)
    assert applied == [
        "settings/ssl",
        "rulesets/http_ratelimit",
        "bot/bot_management",
        "dns/siutindei.com",
    ]
    methods_paths = [(method, path) for method, path, _ in fake.writes]
    assert methods_paths == [
        ("PATCH", "/zones/z1/settings/ssl"),
        ("PUT", "/zones/z1/rulesets/phases/http_ratelimit/entrypoint"),
        ("PUT", "/zones/z1/bot_management"),
        ("PATCH", "/zones/z1/dns_records/rec1"),
    ]
    assert fake.writes[0][2] == {"value": "strict"}
    ruleset_body = fake.writes[1][2]
    assert ruleset_body is not None
    assert ruleset_body["name"] == "Public website rate limits"
    assert ruleset_body["rules"][0]["description"] == "search-per-ip"
    assert fake.writes[2][2] == {"fight_mode": False, "ai_bots_protection": "block"}
    assert fake.writes[3][2] == {"proxied": True}


def test_dns_rollback_override_plans_unproxying():
    policy = _policy({}, proxied=False)
    api, fake = _api(_live_state(policy, proxied=True))
    changes = edge_policy.build_plan(api, "z1", policy, ("dns",))
    assert len(changes) == 1
    assert changes[0].kind == "update"
    edge_policy.apply_plan(api, changes)
    assert fake.writes == [("PATCH", "/zones/z1/dns_records/rec1", {"proxied": False})]


def test_render_masks_the_edge_secret():
    policy = _policy({"PUBLIC_WWW_EDGE_VERIFY_SECRET": _SECRET})
    change = edge_policy.Change("rulesets", "x", "update", f"value {_SECRET} here")
    text = edge_policy.render([change], policy.secrets)
    assert _SECRET not in text
    assert edge_policy.MASK in text


def test_main_refuses_apply_without_yes_and_with_blocked_items(monkeypatch, capsys):
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "token")
    monkeypatch.delenv("PUBLIC_WWW_EDGE_VERIFY_SECRET", raising=False)
    policy = _policy({})
    live = _live_state(policy, proxied=False)
    live["/zones"] = [{"id": "z1", "name": "siutindei.com"}]
    fake = FakeCloudflare(live)
    real_api = edge_policy.CloudflareApi
    monkeypatch.setattr(
        edge_policy,
        "CloudflareApi",
        lambda token: real_api(token, requester=fake),
    )
    assert edge_policy.main(["apply", "--section", "dns"]) == 2
    assert "requires --yes" in capsys.readouterr().err
    assert edge_policy.main(["apply", "--yes", "--section", "rulesets"]) == 1
    assert "apply refused" in capsys.readouterr().err
    assert fake.writes == []
    assert edge_policy.main(["apply", "--yes", "--section", "dns"]) == 0
    assert fake.writes == [("PATCH", "/zones/z1/dns_records/rec1", {"proxied": True})]


@pytest.mark.parametrize("flag", ["--proxied", "--section"])
def test_cli_rejects_unknown_choices(flag):
    with pytest.raises(SystemExit):
        edge_policy.parse_args(["plan", flag, "nonsense"])
