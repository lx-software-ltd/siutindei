"""Stack labels resolve from the plan. All stacks leaves the WAF stack out."""

from __future__ import annotations

import json
from pathlib import Path

PLAN = (
    Path(__file__).resolve().parents[1] / "backend" / "infrastructure" / "cdk-plan.json"
)
ROOT = Path(__file__).resolve().parents[1]


def test_all_stacks_leaves_the_waf_stack_out() -> None:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    known = {
        name
        for group in plan["groups"]
        for name in group["stacks"]
    }
    aliases = plan["aliases"]
    assert "lxsoftware-siutindei-waf" in known
    assert aliases["all stacks"] == [
        "lxsoftware-siutindei",
        "lxsoftware-siutindei-admin-web",
        "lxsoftware-siutindei-public-www",
    ]
    assert aliases["waf (us-east-1)"] == ["lxsoftware-siutindei-waf"]
    assert aliases["lambda apis"] == ["lxsoftware-siutindei"]
    assert all(name in known for names in aliases.values() for name in names)


def test_pull_request_diff_uses_the_read_only_role_and_the_plan() -> None:
    text = (ROOT / ".github" / "workflows" / "cdk-diff.yml").read_text(encoding="utf-8")
    job = text.split("  pull-request:", 1)[1]
    assert "environment: production" not in job
    assert "vars.AWS_DIFF_ROLE_NAME" in job
    assert "GitHubActionsRole is not assumed from a pull request" in job
    assert "stacks: ${{ steps.prep.outputs.stacks }}" in job
    assert 'include-extras: "false"' in job
    assert "plan-file: backend/infrastructure/cdk-plan.json" in job
    prepare = (ROOT / "scripts" / "deploy" / "cdk-prepare.sh").read_text(encoding="utf-8")
    assert 'or "all stacks"' in prepare
