#!/usr/bin/env python3
"""Plan and apply the Cloudflare edge policy for the public website.

The desired state lives in ``public_www_edge_policy.json`` next to this
file. ``plan`` is read-only: it fetches the live zone and prints every
setting, ruleset, bot-management field, and DNS proxy flag that differs.
``apply`` writes the differences, section by section, and refuses to run
without ``--yes``. Every write is idempotent: zone settings are patched,
each ruleset phase entrypoint is replaced as a whole, bot management is
put, and the DNS record is patched.

Placeholders in the policy are ``${NAME}``. ``${HOSTNAME}`` resolves to the
policy ``hostname`` (or ``--hostname``); anything else resolves from the
environment. An unresolved placeholder blocks ``apply`` for the section
that contains it and is reported by ``plan``.

Environment: ``CLOUDFLARE_API_TOKEN`` (required),
``PUBLIC_WWW_EDGE_VERIFY_SECRET`` (transform rule value).

    python3 scripts/cloudflare/edge_policy.py plan
    python3 scripts/cloudflare/edge_policy.py apply --yes --section settings
    python3 scripts/cloudflare/edge_policy.py apply --yes --section dns
    python3 scripts/cloudflare/edge_policy.py apply --yes --section dns --proxied false

Plan: docs/plans/cloudflare-edge-protection.md
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Any

API_BASE = "https://api.cloudflare.com/client/v4"
DEFAULT_POLICY = Path(__file__).with_name("public_www_edge_policy.json")
SECTIONS = ("settings", "rulesets", "bot", "dns")
# Ruleset phases are applied in this order so the request-header secret and
# cache behaviour exist before any blocking rule starts matching.
PHASE_ORDER = (
    "http_request_cache_settings",
    "http_request_late_transform",
    "http_request_firewall_custom",
    "http_ratelimit",
)
RULE_COMPARE_KEYS = (
    "description",
    "expression",
    "action",
    "action_parameters",
    "ratelimit",
    "enabled",
)
PLACEHOLDER = re.compile(r"\$\{([A-Z0-9_]+)\}")
MASK = "<secret>"


class PolicyError(Exception):
    """The policy file or its placeholders cannot be used."""


class ApiError(Exception):
    """Cloudflare returned ``success: false`` or an HTTP error."""

    def __init__(self, status: int, messages: list[str]):
        super().__init__(f"HTTP {status}: {'; '.join(messages) or 'unknown error'}")
        self.status = status
        self.messages = messages


Requester = Callable[[str, str, dict[str, Any] | None], dict[str, Any]]


class CloudflareApi:
    """Minimal JSON client. ``request`` is swappable for tests."""

    def __init__(self, token: str, requester: Requester | None = None):
        self._token = token
        self._requester = requester or self._http

    def request(
        self, method: str, path: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return self._requester(method, path, body)

    def _http(
        self, method: str, path: str, body: dict[str, Any] | None
    ) -> dict[str, Any]:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(
            f"{API_BASE}{path}",
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
                status = response.status
        except urllib.error.HTTPError as error:
            status = error.code
            try:
                payload = json.loads(error.read().decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                payload = {"success": False, "errors": [{"message": error.reason}]}
        if not payload.get("success", False):
            messages = [
                str(item.get("message", item)) for item in payload.get("errors", [])
            ]
            raise ApiError(status, messages)
        return payload


@dataclass
class Policy:
    zone_name: str
    hostname: str
    dns: dict[str, Any]
    settings: dict[str, Any]
    bot_management: dict[str, Any]
    rulesets: dict[str, dict[str, Any]]
    secrets: tuple[str, ...]
    missing: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class Change:
    section: str
    target: str
    kind: str  # noop | update | create | blocked | unreadable
    detail: str
    apply: Callable[[CloudflareApi], None] | None = None


def _substitute(value: Any, variables: Mapping[str, str], missing: set[str]) -> Any:
    if isinstance(value, str):

        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            if name in variables:
                return variables[name]
            missing.add(name)
            return match.group(0)

        return PLACEHOLDER.sub(replace, value)
    if isinstance(value, list):
        return [_substitute(item, variables, missing) for item in value]
    if isinstance(value, dict):
        return {
            key: _substitute(item, variables, missing) for key, item in value.items()
        }
    return value


def load_policy(
    path: Path,
    environ: Mapping[str, str],
    *,
    zone_name: str | None = None,
    hostname: str | None = None,
    proxied: bool | None = None,
) -> Policy:
    raw = json.loads(path.read_text(encoding="utf-8"))
    resolved_hostname = hostname or raw["hostname"]
    variables = {**environ, "HOSTNAME": resolved_hostname}
    secret_names = tuple(
        name for name in set(PLACEHOLDER.findall(json.dumps(raw))) if name != "HOSTNAME"
    )
    missing: dict[str, list[str]] = {}
    sections: dict[str, Any] = {}
    for key in ("dns", "settings", "bot_management"):
        unresolved: set[str] = set()
        sections[key] = _substitute(raw.get(key, {}), variables, unresolved)
        if unresolved:
            missing[key] = sorted(unresolved)
    if proxied is not None:
        sections["dns"]["proxied"] = proxied
    sections["rulesets"] = {}
    for phase, spec in raw.get("rulesets", {}).items():
        if phase not in PHASE_ORDER:
            raise PolicyError(f"unsupported ruleset phase: {phase}")
        unresolved = set()
        sections["rulesets"][phase] = _substitute(spec, variables, unresolved)
        if unresolved:
            missing[f"rulesets:{phase}"] = sorted(unresolved)
    return Policy(
        zone_name=zone_name or raw["zone_name"],
        hostname=resolved_hostname,
        dns=sections["dns"],
        settings=sections["settings"],
        bot_management=sections["bot_management"],
        rulesets=sections["rulesets"],
        secrets=tuple(environ[name] for name in secret_names if environ.get(name, "")),
        missing=missing,
    )


def is_subset(desired: Any, current: Any) -> bool:
    """True when every key in ``desired`` matches ``current`` recursively."""
    if isinstance(desired, dict):
        if not isinstance(current, dict):
            return False
        return all(is_subset(value, current.get(key)) for key, value in desired.items())
    if isinstance(desired, list):
        return (
            isinstance(current, list)
            and len(desired) == len(current)
            and all(is_subset(a, b) for a, b in zip(desired, current, strict=True))
        )
    return desired == current


def normalize_rule(rule: dict[str, Any]) -> dict[str, Any]:
    normalized = {key: rule[key] for key in RULE_COMPARE_KEYS if key in rule}
    normalized.setdefault("enabled", True)
    return normalized


def mask(text: str, secrets: tuple[str, ...]) -> str:
    for secret in secrets:
        if secret:
            text = text.replace(secret, MASK)
    return text


def zone_id_for(api: CloudflareApi, zone_name: str) -> str:
    payload = api.request("GET", f"/zones?name={zone_name}&status=active", None)
    zones = payload.get("result") or []
    if len(zones) != 1:
        raise PolicyError(f"expected one active zone named {zone_name}")
    return str(zones[0]["id"])


def _unreadable(section: str, target: str, error: ApiError) -> Change:
    return Change(section, target, "unreadable", str(error))


def plan_settings(api: CloudflareApi, zone_id: str, policy: Policy) -> list[Change]:
    changes: list[Change] = []
    for setting, desired in policy.settings.items():
        try:
            current = api.request("GET", f"/zones/{zone_id}/settings/{setting}", None)[
                "result"
            ]["value"]
        except ApiError as error:
            changes.append(_unreadable("settings", setting, error))
            continue
        if current == desired:
            changes.append(Change("settings", setting, "noop", json.dumps(desired)))
            continue

        def apply(
            client: CloudflareApi, name: str = setting, value: Any = desired
        ) -> None:
            client.request(
                "PATCH", f"/zones/{zone_id}/settings/{name}", {"value": value}
            )

        changes.append(
            Change(
                "settings",
                setting,
                "update",
                f"{json.dumps(current)} -> {json.dumps(desired)}",
                apply,
            )
        )
    return changes


def plan_rulesets(api: CloudflareApi, zone_id: str, policy: Policy) -> list[Change]:
    changes: list[Change] = []
    for phase in PHASE_ORDER:
        if phase not in policy.rulesets:
            continue
        spec = policy.rulesets[phase]
        desired_rules = [normalize_rule(rule) for rule in spec["rules"]]
        blocked = policy.missing.get(f"rulesets:{phase}", [])
        if blocked:
            changes.append(
                Change(
                    "rulesets",
                    phase,
                    "blocked",
                    f"unresolved placeholders: {', '.join(blocked)}",
                )
            )
            continue
        try:
            payload = api.request(
                "GET", f"/zones/{zone_id}/rulesets/phases/{phase}/entrypoint", None
            )
            current_rules = [
                normalize_rule(rule) for rule in payload["result"].get("rules", [])
            ]
            exists = True
        except ApiError as error:
            if error.status == 404:
                current_rules, exists = [], False
            else:
                changes.append(_unreadable("rulesets", phase, error))
                continue
        if exists and is_subset(desired_rules, current_rules):
            changes.append(
                Change("rulesets", phase, "noop", f"{len(desired_rules)} rule(s)")
            )
            continue

        names = ", ".join(rule["description"] for rule in desired_rules)
        changes.append(
            Change(
                "rulesets",
                phase,
                "update" if exists else "create",
                f"{len(current_rules)} -> {len(desired_rules)} rule(s): {names}",
                partial(_put_ruleset, zone_id, phase, spec),
            )
        )
    return changes


def _put_ruleset(
    zone_id: str, phase: str, spec: dict[str, Any], client: CloudflareApi
) -> None:
    client.request(
        "PUT",
        f"/zones/{zone_id}/rulesets/phases/{phase}/entrypoint",
        {
            "name": spec["name"],
            "description": "Managed by scripts/cloudflare/edge_policy.py",
            "rules": spec["rules"],
        },
    )


def plan_bot(api: CloudflareApi, zone_id: str, policy: Policy) -> list[Change]:
    if not policy.bot_management:
        return []
    try:
        current = api.request("GET", f"/zones/{zone_id}/bot_management", None)["result"]
    except ApiError as error:
        return [_unreadable("bot", "bot_management", error)]
    if is_subset(policy.bot_management, current):
        return [
            Change("bot", "bot_management", "noop", json.dumps(policy.bot_management))
        ]
    diff = {
        key: f"{json.dumps(current.get(key))} -> {json.dumps(value)}"
        for key, value in policy.bot_management.items()
        if current.get(key) != value
    }

    def apply(client: CloudflareApi) -> None:
        client.request("PUT", f"/zones/{zone_id}/bot_management", policy.bot_management)

    return [Change("bot", "bot_management", "update", json.dumps(diff), apply)]


def plan_dns(api: CloudflareApi, zone_id: str, policy: Policy) -> list[Change]:
    name = policy.dns["name"]
    record_type = policy.dns["type"]
    desired = bool(policy.dns["proxied"])
    try:
        records = api.request(
            "GET", f"/zones/{zone_id}/dns_records?name={name}&type={record_type}", None
        )["result"]
    except ApiError as error:
        return [_unreadable("dns", name, error)]
    if len(records) != 1:
        return [
            Change(
                "dns",
                name,
                "blocked",
                f"expected one {record_type} record, found {len(records)}",
            )
        ]
    record = records[0]
    if bool(record.get("proxied")) == desired:
        return [Change("dns", name, "noop", f"proxied {json.dumps(desired)}")]
    if desired and not record.get("proxiable", True):
        return [Change("dns", name, "blocked", "record is not proxiable")]

    def apply(client: CloudflareApi) -> None:
        client.request(
            "PATCH",
            f"/zones/{zone_id}/dns_records/{record['id']}",
            {"proxied": desired},
        )

    return [
        Change(
            "dns",
            name,
            "update",
            f"proxied {json.dumps(bool(record.get('proxied')))} -> {json.dumps(desired)}"
            f" ({record.get('content')})",
            apply,
        )
    ]


PLANNERS = {
    "settings": plan_settings,
    "rulesets": plan_rulesets,
    "bot": plan_bot,
    "dns": plan_dns,
}


def build_plan(
    api: CloudflareApi, zone_id: str, policy: Policy, sections: tuple[str, ...]
) -> list[Change]:
    changes: list[Change] = []
    for section in SECTIONS:
        if section in sections:
            changes.extend(PLANNERS[section](api, zone_id, policy))
    return changes


def render(changes: list[Change], secrets: tuple[str, ...]) -> str:
    width = max((len(change.target) for change in changes), default=10)
    lines = [f"{'section':<9} {'target':<{width}} {'status':<10} detail"]
    for change in changes:
        lines.append(
            f"{change.section:<9} {change.target:<{width}} {change.kind:<10} "
            f"{mask(change.detail, secrets)}"
        )
    pending = sum(change.kind in {"update", "create"} for change in changes)
    blocked = sum(change.kind in {"blocked", "unreadable"} for change in changes)
    lines.append(f"{pending} change(s) pending, {blocked} blocked or unreadable.")
    return "\n".join(lines)


def apply_plan(api: CloudflareApi, changes: list[Change]) -> list[str]:
    applied: list[str] = []
    for change in changes:
        if change.apply is None:
            continue
        change.apply(api)
        applied.append(f"{change.section}/{change.target}")
    return applied


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=("plan", "apply"))
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--zone", help="Override the policy zone_name.")
    parser.add_argument("--hostname", help="Override the policy hostname.")
    parser.add_argument(
        "--section",
        action="append",
        choices=SECTIONS,
        help="Limit to one or more sections. Default: all.",
    )
    parser.add_argument(
        "--proxied",
        choices=("true", "false"),
        help="Override the DNS proxied flag (rollback: --section dns --proxied false).",
    )
    parser.add_argument("--yes", action="store_true", help="Required for apply.")
    parser.add_argument("--json", action="store_true", help="Machine-readable output.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    if not token:
        print("CLOUDFLARE_API_TOKEN is not set.", file=sys.stderr)
        return 2
    proxied = None if args.proxied is None else args.proxied == "true"
    policy = load_policy(
        args.policy,
        os.environ,
        zone_name=args.zone,
        hostname=args.hostname,
        proxied=proxied,
    )
    sections = tuple(args.section) if args.section else SECTIONS
    api = CloudflareApi(token)
    zone_id = zone_id_for(api, policy.zone_name)
    changes = build_plan(api, zone_id, policy, sections)
    if args.json:
        print(
            json.dumps(
                [
                    {
                        "section": c.section,
                        "target": c.target,
                        "status": c.kind,
                        "detail": mask(c.detail, policy.secrets),
                    }
                    for c in changes
                ],
                indent=2,
            )
        )
    else:
        print(f"zone {policy.zone_name} ({zone_id}), hostname {policy.hostname}")
        print(render(changes, policy.secrets))
    if args.command == "plan":
        return 0
    if not args.yes:
        print("apply requires --yes.", file=sys.stderr)
        return 2
    if any(change.kind in {"blocked", "unreadable"} for change in changes):
        print(
            "apply refused: resolve blocked or unreadable items first.", file=sys.stderr
        )
        return 1
    applied = apply_plan(api, changes)
    print(f"applied {len(applied)}: {', '.join(applied) or 'nothing'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
