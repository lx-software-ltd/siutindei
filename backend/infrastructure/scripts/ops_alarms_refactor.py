#!/usr/bin/env python3
"""Move the ops alarms from the API stack into its OpsAlarmsStack nested stack.

One-off CloudFormation stack refactor; see
docs/deployment/ops-alarms-stack-refactor.md. Needs only Python 3.9+ and the
AWS CLI (v2, or a v1 release that has the stack refactor commands), so it runs
in AWS CloudShell as a single uploaded file.

  python3 ops_alarms_refactor.py preview
      Validates, uploads the templates and creates the refactor. Creating a
      refactor only previews it; nothing in either stack changes.
  python3 ops_alarms_refactor.py execute WORK_DIR
      Executes the previewed refactor after confirmation, then verifies it.
  python3 ops_alarms_refactor.py build --parent P --nested N --out DIR
      Offline: builds the refactor templates from two template files.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PARENT_STACK = "lxsoftware-siutindei"
DEFAULT_REGION = "ap-southeast-1"
NESTED_LOGICAL_ID_PREFIX = "OpsAlarmsStack"
EXPECTED_ALARM_COUNT = 16
READY_STACK_STATUSES = {"CREATE_COMPLETE", "UPDATE_COMPLETE"}
POLL_SECONDS = 5
POLL_TIMEOUT_SECONDS = 30 * 60

# Pseudo parameters with the same value in the parent and the nested stack.
# Stack refactoring rejects resources using ones that differ, such as
# AWS::StackName.
STACK_INDEPENDENT_PSEUDO_PARAMETERS = {
    "AWS::AccountId",
    "AWS::Partition",
    "AWS::Region",
    "AWS::URLSuffix",
}


class RefactorError(Exception):
    pass


# ---------------------------------------------------------------------------
# Template transform (no AWS calls)
# ---------------------------------------------------------------------------


def collect_references(value: Any, found: set[str]) -> None:
    """Collect Ref and Fn::GetAtt targets, plus any Fn::Sub or Fn::ImportValue."""
    if isinstance(value, list):
        for item in value:
            collect_references(item, found)
        return
    if not isinstance(value, dict):
        return
    for key, child in value.items():
        if key == "Ref" and isinstance(child, str):
            found.add(child)
        elif key == "Fn::GetAtt":
            found.add(
                str(child[0]) if isinstance(child, list) else str(child).split(".")[0]
            )
        elif key in ("Fn::Sub", "Fn::ImportValue"):
            found.add(key)
        collect_references(child, found)


def external_references(resource: dict[str, Any]) -> list[str]:
    found: set[str] = set()
    collect_references({k: v for k, v in resource.items() if k != "Metadata"}, found)
    return sorted(found - STACK_INDEPENDENT_PSEUDO_PARAMETERS)


def is_ops_alarm_rule(resource: dict[str, Any]) -> bool:
    cdk_path = (resource.get("Metadata") or {}).get("aws:cdk:path")
    if resource.get("Type") != "AWS::CloudWatch::Alarm" or not isinstance(
        cdk_path, str
    ):
        return False
    segments = cdk_path.split("/")
    return len(segments) == 4 and segments[1] == "OpsAlarms"


def _mentions(value: Any, logical_id: str) -> bool:
    text = json.dumps(value)
    return (
        f'"{logical_id}"' in text
        or f"${{{logical_id}}}" in text
        or f"${{{logical_id}." in text
    )


def parse_template(raw: Any, label: str) -> dict[str, Any]:
    template = json.loads(raw) if isinstance(raw, str) else raw
    if isinstance(template, str):
        template = json.loads(template)
    if not isinstance(template, dict) or not isinstance(
        template.get("Resources"), dict
    ):
        raise RefactorError(f"{label} is not a CloudFormation JSON template")
    return template


def build_refactor(
    parent: dict[str, Any],
    nested: dict[str, Any],
    parent_stack: str,
    nested_stack: str,
) -> dict[str, Any]:
    """Move the ops alarm rules verbatim from the parent template to the nested one."""
    resources = parent["Resources"]
    moved = sorted(i for i, r in resources.items() if is_ops_alarm_rule(r))
    problems = []
    if len(moved) != EXPECTED_ALARM_COUNT:
        problems.append(
            f"expected {EXPECTED_ALARM_COUNT} ops alarms in the parent, found {len(moved)}"
        )
    for logical_id in moved:
        resource = resources[logical_id]
        refs = external_references(resource)
        if refs:
            problems.append(f"{logical_id} references {', '.join(refs)}")
        if "DependsOn" in resource or "Condition" in resource:
            problems.append(f"{logical_id} has DependsOn or Condition")
        if logical_id in nested["Resources"]:
            problems.append(f"{logical_id} already exists in the nested template")

    moved_set = set(moved)
    for logical_id, resource in resources.items():
        if logical_id in moved_set:
            continue
        body = {k: v for k, v in resource.items() if k != "Metadata"}
        problems += [
            f"{logical_id} still references {t}" for t in moved if _mentions(body, t)
        ]
    for section, body in parent.items():
        if section != "Resources":
            problems += [
                f"parent {section} references {t}" for t in moved if _mentions(body, t)
            ]
    if problems:
        raise RefactorError(
            "Refusing to build the refactor:\n- " + "\n- ".join(problems)
        )

    return {
        "moved": moved,
        "parent": {
            **parent,
            "Resources": {i: r for i, r in resources.items() if i not in moved_set},
        },
        "nested": {
            **nested,
            "Resources": {**nested["Resources"], **{i: resources[i] for i in moved}},
        },
        "resource_mappings": [
            {
                "Source": {"StackName": parent_stack, "LogicalResourceId": i},
                "Destination": {"StackName": nested_stack, "LogicalResourceId": i},
            }
            for i in moved
        ],
    }


def check_refactor_actions(
    actions: list[dict[str, Any]], moved_physical_ids: dict[str, str]
) -> list[str]:
    """Problems with a refactor preview; empty when it only moves the ops alarms."""
    problems = []
    for action in actions:
        if action.get("Action") != "MOVE":
            problems.append(f"unexpected {action.get('Action')} action: {action}")
    physical_to_logical = {p: i for i, p in moved_physical_ids.items()}
    seen = []
    for action in actions:
        if action.get("Entity") != "RESOURCE":
            continue
        source = (action.get("ResourceMapping") or {}).get("Source") or {}
        logical_id = source.get("LogicalResourceId") or physical_to_logical.get(
            str(action.get("PhysicalResourceId"))
        )
        if logical_id not in moved_physical_ids:
            problems.append(f"unexpected resource in the refactor: {action}")
        seen.append(logical_id)
    if sorted(seen) != sorted(moved_physical_ids):
        problems.append(
            f"expected one move for each of the {len(moved_physical_ids)} alarms, got {len(seen)}"
        )
    return problems


def template_bucket(parent: dict[str, Any], nested_logical_id: str) -> str:
    """The CDK assets bucket, read from the nested stack's TemplateURL."""
    url = parent["Resources"][nested_logical_id]["Properties"]["TemplateURL"]
    parts = url["Fn::Join"][1] if isinstance(url, dict) else [url]
    path = "".join(p for p in parts if isinstance(p, str))
    segments = [s for s in path.split("/") if s]
    if len(segments) < 2:
        raise RefactorError(f"Cannot read the assets bucket from TemplateURL {url}")
    return segments[-2]


def _write_json(path: Path, body: Any) -> None:
    path.write_text(json.dumps(body, separators=(",", ":")) + "\n")


# ---------------------------------------------------------------------------
# AWS CLI
# ---------------------------------------------------------------------------


class Aws:
    def __init__(self, region: str):
        self.region = region

    def __call__(self, *args: str) -> Any:
        command = ["aws", *args, "--region", self.region, "--output", "json"]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            env={**os.environ, "AWS_PAGER": ""},
            check=False,
        )
        if result.returncode != 0:
            raise RefactorError(
                f"aws {' '.join(args[:2])} failed:\n{result.stderr.strip()}"
            )
        return json.loads(result.stdout) if result.stdout.strip() else None

    def stack_resources(self, stack: str) -> list[dict[str, Any]]:
        # describe-stack-resources stops at 100 resources; the parent has ~500.
        return self("cloudformation", "list-stack-resources", "--stack-name", stack)[
            "StackResourceSummaries"
        ]

    def stack_status(self, stack: str) -> tuple[str, str]:
        found = self("cloudformation", "describe-stacks", "--stack-name", stack)[
            "Stacks"
        ][0]
        return found["StackName"], found["StackStatus"]

    def template(self, stack: str) -> dict[str, Any]:
        body = self(
            "cloudformation",
            "get-template",
            "--stack-name",
            stack,
            "--template-stage",
            "Original",
        )["TemplateBody"]
        return parse_template(body, stack)

    def alarm_names(self, prefix: str) -> list[str]:
        alarms = self("cloudwatch", "describe-alarms", "--alarm-name-prefix", prefix)
        return sorted(a["AlarmName"] for a in alarms["MetricAlarms"])

    def describe_refactor(self, refactor_id: str) -> dict[str, Any]:
        return self(
            "cloudformation",
            "describe-stack-refactor",
            "--stack-refactor-id",
            refactor_id,
        )

    def wait_refactor(self, refactor_id: str, field: str) -> dict[str, Any]:
        deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
        while True:
            refactor = self.describe_refactor(refactor_id)
            if not str(refactor.get(field, "")).endswith("_IN_PROGRESS"):
                return refactor
            if time.monotonic() > deadline:
                raise RefactorError(
                    f"Timed out waiting on {field} of refactor {refactor_id}"
                )
            time.sleep(POLL_SECONDS)


def _require_stack_refactor_support(aws: Aws) -> None:
    try:
        aws("cloudformation", "list-stack-refactors")
    except RefactorError as error:
        raise RefactorError(
            "This AWS CLI cannot run stack refactors. Use AWS CloudShell, or upgrade "
            f"the CLI.\n{error}"
        ) from error


def _find_nested_stack(aws: Aws) -> tuple[str, str]:
    matches = [
        r
        for r in aws.stack_resources(PARENT_STACK)
        if r["ResourceType"] == "AWS::CloudFormation::Stack"
        and r["LogicalResourceId"].startswith(NESTED_LOGICAL_ID_PREFIX)
    ]
    if len(matches) != 1:
        raise RefactorError(
            f"Expected one {NESTED_LOGICAL_ID_PREFIX} nested stack in {PARENT_STACK}, "
            f"found {len(matches)}. Is stage 1 deployed?"
        )
    return matches[0]["LogicalResourceId"], matches[0]["PhysicalResourceId"]


def _require_ready(aws: Aws, stack: str) -> str:
    name, status = aws.stack_status(stack)
    if status not in READY_STACK_STATUSES:
        raise RefactorError(
            f"{name} is {status}; wait for it to be CREATE or UPDATE_COMPLETE"
        )
    print(f"  {name}: {status}")
    return name


def _print_actions(actions: list[dict[str, Any]]) -> None:
    for action in actions:
        source = (action.get("ResourceMapping") or {}).get("Source") or {}
        print(
            f"  {action.get('Action', '?'):6} {action.get('Entity', '?'):8} "
            f"{source.get('LogicalResourceId', '')} {action.get('PhysicalResourceId', '')}"
        )


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def preview(args: argparse.Namespace) -> None:
    aws = Aws(args.region)
    _require_stack_refactor_support(aws)
    identity = aws("sts", "get-caller-identity")
    account = identity["Account"]
    print(f"Account {account}, region {args.region}, as {identity['Arn']}")

    print("Checking stacks")
    nested_logical_id, nested_arn = _find_nested_stack(aws)
    _require_ready(aws, PARENT_STACK)
    nested_stack = _require_ready(aws, nested_arn)

    parent_template = aws.template(PARENT_STACK)
    nested_template = aws.template(nested_stack)
    refactor = build_refactor(
        parent_template, nested_template, PARENT_STACK, nested_stack
    )
    moved = refactor["moved"]

    deployed = {r["LogicalResourceId"]: r for r in aws.stack_resources(PARENT_STACK)}
    missing = [i for i in moved if i not in deployed]
    if missing:
        raise RefactorError(f"Not deployed in {PARENT_STACK}: {', '.join(missing)}")
    moved_physical_ids = {i: deployed[i]["PhysicalResourceId"] for i in moved}
    alarms_before = aws.alarm_names(f"{PARENT_STACK}-")
    print(
        f"Moving {len(moved)} alarms: parent {len(refactor['parent']['Resources'])} "
        f"resources, nested {len(refactor['nested']['Resources'])} resources"
    )

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    work_dir = Path(args.work_dir or Path.home() / f"ops-alarms-refactor-{stamp}")
    work_dir.mkdir(parents=True, exist_ok=False)
    _write_json(work_dir / "parent.deployed.json", parent_template)
    _write_json(work_dir / "nested.deployed.json", nested_template)
    _write_json(work_dir / "parent.json", refactor["parent"])
    _write_json(work_dir / "nested.json", refactor["nested"])
    _write_json(work_dir / "resource-mappings.json", refactor["resource_mappings"])

    bucket = args.bucket or template_bucket(parent_template, nested_logical_id)
    prefix = f"stack-refactor/ops-alarms-{stamp}"
    keys = {name: f"{prefix}/{name}.json" for name in ("parent", "nested")}
    for name, key in keys.items():
        aws(
            "s3api",
            "put-object",
            "--bucket",
            bucket,
            "--key",
            key,
            "--body",
            str(work_dir / f"{name}.json"),
        )
    url = f"https://{bucket}.s3.{args.region}.amazonaws.com"
    _write_json(
        work_dir / "stack-definitions.json",
        [
            {"StackName": PARENT_STACK, "TemplateURL": f"{url}/{keys['parent']}"},
            {"StackName": nested_stack, "TemplateURL": f"{url}/{keys['nested']}"},
        ],
    )
    print(f"Uploaded templates to s3://{bucket}/{prefix}/")

    refactor_id = aws(
        "cloudformation",
        "create-stack-refactor",
        "--description",
        "Move ops alarms into OpsAlarmsStack",
        "--no-enable-stack-creation",
        "--stack-definitions",
        f"file://{work_dir / 'stack-definitions.json'}",
        "--resource-mappings",
        f"file://{work_dir / 'resource-mappings.json'}",
    )["StackRefactorId"]
    state = {
        "region": args.region,
        "refactor_id": refactor_id,
        "parent_stack": PARENT_STACK,
        "nested_stack": nested_stack,
        "bucket": bucket,
        "keys": list(keys.values()),
        "moved": moved_physical_ids,
        "alarms_before": alarms_before,
    }
    _write_json(work_dir / "state.json", state)
    print(f"Created refactor {refactor_id}; waiting for validation")

    described = aws.wait_refactor(refactor_id, "Status")
    if described.get("Status") != "CREATE_COMPLETE":
        raise RefactorError(
            f"Refactor {described.get('Status')}: {described.get('StatusReason')}\n"
            "Nothing has changed."
        )
    actions = aws(
        "cloudformation",
        "list-stack-refactor-actions",
        "--stack-refactor-id",
        refactor_id,
    )["StackRefactorActions"]
    _print_actions(actions)
    problems = check_refactor_actions(actions, moved_physical_ids)
    if described.get("ExecutionStatus") != "AVAILABLE":
        problems.append(f"ExecutionStatus is {described.get('ExecutionStatus')}")
    if problems:
        raise RefactorError(
            "The preview is not a pure move of the ops alarms. Do not execute it.\n- "
            + "\n- ".join(problems)
        )
    print(
        f"\nPreview OK: {len(moved)} alarm moves and nothing else. Nothing has changed yet.\n"
        f"To run it:\n  python3 {sys.argv[0]} execute {work_dir}"
    )


def execute(args: argparse.Namespace) -> None:
    work_dir = Path(args.work_dir)
    state = json.loads((work_dir / "state.json").read_text())
    aws = Aws(state["region"])
    refactor_id = state["refactor_id"]
    moved: dict[str, str] = state["moved"]

    described = aws.describe_refactor(refactor_id)
    if described.get("Status") != "CREATE_COMPLETE" or described.get(
        "ExecutionStatus"
    ) != ("AVAILABLE"):
        raise RefactorError(
            f"Refactor {refactor_id} is {described.get('Status')} / "
            f"{described.get('ExecutionStatus')}; run preview again."
        )
    if not args.yes:
        answer = input(
            f"Move {len(moved)} alarms from {state['parent_stack']} into "
            f"{state['nested_stack']}? Type EXECUTE to continue: "
        )
        if answer.strip() != "EXECUTE":
            raise RefactorError("Not confirmed; nothing changed.")

    aws("cloudformation", "execute-stack-refactor", "--stack-refactor-id", refactor_id)
    print(f"Executing refactor {refactor_id}")
    described = aws.wait_refactor(refactor_id, "ExecutionStatus")
    if described.get("ExecutionStatus") != "EXECUTE_COMPLETE":
        raise RefactorError(
            f"Execution {described.get('ExecutionStatus')}: "
            f"{described.get('ExecutionStatusReason')}\nDo not merge stage 3."
        )

    nested_ids = {
        r["LogicalResourceId"] for r in aws.stack_resources(state["nested_stack"])
    }
    parent_ids = {
        r["LogicalResourceId"] for r in aws.stack_resources(state["parent_stack"])
    }
    alarms_after = aws.alarm_names(f"{state['parent_stack']}-")
    problems = []
    if not set(moved) <= nested_ids:
        problems.append(
            f"missing from the nested stack: {sorted(set(moved) - nested_ids)}"
        )
    if set(moved) & parent_ids:
        problems.append(f"still in the parent stack: {sorted(set(moved) & parent_ids)}")
    if alarms_after != state["alarms_before"]:
        problems.append("the set of alarm names changed")
    if problems:
        raise RefactorError(
            "Refactor executed but verification failed:\n- " + "\n- ".join(problems)
        )

    for key in state["keys"]:
        aws("s3api", "delete-object", "--bucket", state["bucket"], "--key", key)
    print(
        f"Done: {len(moved)} alarms now belong to {state['nested_stack']}, "
        f"and all {len(alarms_after)} alarms still exist. Stage 3 can merge."
    )


def build(args: argparse.Namespace) -> None:
    parent = parse_template(Path(args.parent).read_text(), args.parent)
    nested = parse_template(Path(args.nested).read_text(), args.nested)
    refactor = build_refactor(parent, nested, args.parent_stack, args.nested_stack)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    _write_json(out / "parent.json", refactor["parent"])
    _write_json(out / "nested.json", refactor["nested"])
    _write_json(out / "resource-mappings.json", refactor["resource_mappings"])
    print(
        f"Moving {len(refactor['moved'])} alarms: parent {len(refactor['parent']['Resources'])} "
        f"resources, nested {len(refactor['nested']['Resources'])} resources"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)

    preview_parser = commands.add_parser(
        "preview", help="validate and preview; changes nothing"
    )
    preview_parser.add_argument("--region", default=DEFAULT_REGION)
    preview_parser.add_argument("--bucket", help="override the CDK assets bucket")
    preview_parser.add_argument(
        "--work-dir", help="default: ~/ops-alarms-refactor-<time>"
    )
    preview_parser.set_defaults(run=preview)

    execute_parser = commands.add_parser("execute", help="execute a previewed refactor")
    execute_parser.add_argument("work_dir")
    execute_parser.add_argument(
        "--yes", action="store_true", help="skip the confirmation"
    )
    execute_parser.set_defaults(run=execute)

    build_parser = commands.add_parser("build", help="offline template build")
    build_parser.add_argument("--parent", required=True)
    build_parser.add_argument("--nested", required=True)
    build_parser.add_argument("--parent-stack", default=PARENT_STACK)
    build_parser.add_argument("--nested-stack", default="nested")
    build_parser.add_argument("--out", required=True)
    build_parser.set_defaults(run=build)

    args = parser.parse_args(argv)
    try:
        args.run(args)
    except RefactorError as error:
        print(f"\nERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
