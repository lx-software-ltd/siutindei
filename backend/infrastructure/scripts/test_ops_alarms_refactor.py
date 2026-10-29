"""Tests for ops_alarms_refactor.py against a fake AWS CLI."""

from __future__ import annotations

import copy
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ops_alarms_refactor as refactor  # noqa: E402

PARENT = refactor.PARENT_STACK
NESTED = f"{PARENT}-OpsAlarmsStackABC-XYZ"
NESTED_LOGICAL_ID = "OpsAlarmsStackNestedStackOpsAlarmsStackNestedStackResourceCF60D8C1"
BUCKET = "cdk-hnb659fds-assets-111111111111-ap-southeast-1"
TOPIC_ARN = {
    "Fn::Join": [
        "",
        [
            "arn:",
            {"Ref": "AWS::Partition"},
            f":sns:ap-southeast-1:111111111111:{PARENT}-ops-alerts",
        ],
    ]
}


def alarm(index: int) -> dict[str, Any]:
    return {
        "Type": "AWS::CloudWatch::Alarm",
        "Properties": {
            "AlarmName": f"{PARENT}-alarm-{index}",
            "AlarmActions": [TOPIC_ARN],
            "Dimensions": [{"Name": "FunctionName", "Value": f"{PARENT}-Fn{index}"}],
        },
        "Metadata": {"aws:cdk:path": f"{PARENT}/OpsAlarms/Alarm{index}/Resource"},
    }


def templates() -> tuple[dict[str, Any], dict[str, Any]]:
    resources: dict[str, Any] = {f"OpsAlarmsAlarm{i}": alarm(i) for i in range(16)}
    resources["OpsAlarmsOpsAlertsTopic"] = {"Type": "AWS::SNS::Topic", "Properties": {}}
    resources["ManagerRequestDLQAlarm"] = {
        "Type": "AWS::CloudWatch::Alarm",
        "Properties": {
            "AlarmName": f"{PARENT}-manager-request-dlq-alarm",
            "AlarmActions": [{"Ref": "OpsAlarmsOpsAlertsTopic"}],
        },
        "Metadata": {"aws:cdk:path": f"{PARENT}/ManagerRequestDLQAlarm/Resource"},
    }
    resources[NESTED_LOGICAL_ID] = {
        "Type": "AWS::CloudFormation::Stack",
        "Properties": {
            "TemplateURL": {
                "Fn::Join": [
                    "",
                    [
                        "https://s3.ap-southeast-1.",
                        {"Ref": "AWS::URLSuffix"},
                        f"/{BUCKET}/abc.json",
                    ],
                ]
            }
        },
    }
    parent = {
        "Parameters": {"OpsAlertsEmail": {"Type": "String"}},
        "Resources": resources,
    }
    nested = {
        "Resources": {
            "RefactorPlaceholder": {"Type": "AWS::CloudFormation::WaitConditionHandle"}
        }
    }
    return parent, nested


class FakeAws:
    """Answers the AWS CLI calls the script makes, from in-memory stacks."""

    def __init__(self, parent: dict[str, Any], nested: dict[str, Any]):
        self.templates = {PARENT: parent, NESTED: nested}
        self.refactor: dict[str, Any] = {}
        self.mappings: list[dict[str, Any]] = []
        self.calls: list[tuple[str, ...]] = []
        self.objects: set[str] = set()
        self.fail_execution = False

    def _arg(self, args: tuple[str, ...], flag: str) -> str:
        return args[args.index(flag) + 1]

    def _stack(self, args: tuple[str, ...]) -> str:
        name = self._arg(args, "--stack-name")
        return NESTED if name in (NESTED, f"arn:{NESTED}") else name

    def _summaries(self, stack: str) -> list[dict[str, Any]]:
        summaries = []
        for logical_id, resource in self.templates[stack]["Resources"].items():
            physical = resource.get("Properties", {}).get("AlarmName", logical_id)
            if logical_id == NESTED_LOGICAL_ID:
                physical = f"arn:{NESTED}"
            summaries.append(
                {
                    "LogicalResourceId": logical_id,
                    "PhysicalResourceId": physical,
                    "ResourceType": resource["Type"],
                }
            )
        return summaries

    def alarm_names(self) -> list[str]:
        return sorted(
            r["Properties"]["AlarmName"]
            for t in self.templates.values()
            for r in t["Resources"].values()
            if r["Type"] == "AWS::CloudWatch::Alarm"
        )

    def __call__(self, _aws: refactor.Aws, *args: str) -> Any:
        self.calls.append(args)
        service, command = args[0], args[1]
        if command == "list-stack-refactors":
            return {"StackRefactorSummaries": []}
        if command == "get-caller-identity":
            return {
                "Account": "111111111111",
                "Arn": "arn:aws:iam::111111111111:user/ops",
            }
        if command == "list-stack-resources":
            return {"StackResourceSummaries": self._summaries(self._stack(args))}
        if command == "describe-stacks":
            return {
                "Stacks": [
                    {"StackName": self._stack(args), "StackStatus": "UPDATE_COMPLETE"}
                ]
            }
        if command == "get-template":
            return {"TemplateBody": copy.deepcopy(self.templates[self._stack(args)])}
        if command == "describe-alarms":
            return {"MetricAlarms": [{"AlarmName": n} for n in self.alarm_names()]}
        if command == "put-object":
            self.objects.add(self._arg(args, "--key"))
            return {"ETag": "x"}
        if command == "delete-object":
            self.objects.discard(self._arg(args, "--key"))
            return {}
        if command == "create-stack-refactor":
            mappings_path = self._arg(args, "--resource-mappings").removeprefix(
                "file://"
            )
            self.mappings = json.loads(Path(mappings_path).read_text())
            self.refactor = {
                "Status": "CREATE_COMPLETE",
                "ExecutionStatus": "AVAILABLE",
            }
            return {"StackRefactorId": "refactor-1"}
        if command == "describe-stack-refactor":
            return dict(self.refactor)
        if command == "list-stack-refactor-actions":
            return {
                "StackRefactorActions": [
                    {"Action": "MOVE", "Entity": "RESOURCE", "ResourceMapping": m}
                    for m in self.mappings
                ]
            }
        if command == "execute-stack-refactor" and self.fail_execution:
            self.refactor["ExecutionStatus"] = "EXECUTE_FAILED"
            self.refactor["ExecutionStatusReason"] = "boom"
            return None
        if command == "execute-stack-refactor":
            for mapping in self.mappings:
                logical_id = mapping["Source"]["LogicalResourceId"]
                resource = self.templates[PARENT]["Resources"].pop(logical_id)
                self.templates[NESTED]["Resources"][logical_id] = resource
            self.refactor["ExecutionStatus"] = "EXECUTE_COMPLETE"
            return None
        raise AssertionError(f"unexpected aws call: {service} {command}")


def run(argv: list[str]) -> tuple[int, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = refactor.main(argv)
    return code, out.getvalue() + err.getvalue()


class BuildRefactorTests(unittest.TestCase):
    def test_moves_the_ops_alarms_verbatim(self) -> None:
        parent, nested = templates()
        result = refactor.build_refactor(parent, nested, PARENT, NESTED)
        self.assertEqual(len(result["moved"]), 16)
        self.assertNotIn("OpsAlarmsAlarm0", result["parent"]["Resources"])
        self.assertIn("ManagerRequestDLQAlarm", result["parent"]["Resources"])
        self.assertEqual(result["nested"]["Resources"]["OpsAlarmsAlarm0"], alarm(0))
        self.assertEqual(result["parent"]["Parameters"], parent["Parameters"])

    def test_refuses_an_alarm_with_a_reference(self) -> None:
        parent, nested = templates()
        parent["Resources"]["OpsAlarmsAlarm3"]["Properties"]["Dimensions"][0][
            "Value"
        ] = {"Ref": "SomeFunction"}
        with self.assertRaisesRegex(
            refactor.RefactorError, "OpsAlarmsAlarm3 references"
        ):
            refactor.build_refactor(parent, nested, PARENT, NESTED)

    def test_refuses_when_something_references_an_alarm(self) -> None:
        parent, nested = templates()
        parent["Outputs"] = {"X": {"Value": {"Fn::GetAtt": ["OpsAlarmsAlarm1", "Arn"]}}}
        with self.assertRaisesRegex(
            refactor.RefactorError, "parent Outputs references"
        ):
            refactor.build_refactor(parent, nested, PARENT, NESTED)

    def test_reads_the_assets_bucket_from_the_nested_stack(self) -> None:
        parent, _ = templates()
        self.assertEqual(refactor.template_bucket(parent, NESTED_LOGICAL_ID), BUCKET)


class CheckRefactorActionsTests(unittest.TestCase):
    moved = {f"OpsAlarmsAlarm{i}": f"{PARENT}-alarm-{i}" for i in range(16)}

    def actions(self) -> list[dict[str, Any]]:
        return [
            {
                "Action": "MOVE",
                "Entity": "RESOURCE",
                "ResourceMapping": {"Source": {"LogicalResourceId": logical_id}},
            }
            for logical_id in self.moved
        ]

    def test_accepts_one_move_per_alarm(self) -> None:
        self.assertEqual(
            refactor.check_refactor_actions(self.actions(), self.moved), []
        )

    def test_matches_on_physical_id_without_a_mapping(self) -> None:
        actions = [
            {"Action": "MOVE", "Entity": "RESOURCE", "PhysicalResourceId": p}
            for p in self.moved.values()
        ]
        self.assertEqual(refactor.check_refactor_actions(actions, self.moved), [])

    def test_rejects_a_create(self) -> None:
        actions = self.actions() + [{"Action": "CREATE", "Entity": "STACK"}]
        self.assertTrue(refactor.check_refactor_actions(actions, self.moved))

    def test_rejects_a_missing_or_extra_resource(self) -> None:
        self.assertTrue(refactor.check_refactor_actions(self.actions()[1:], self.moved))
        extra = self.actions() + [
            {
                "Action": "MOVE",
                "Entity": "RESOURCE",
                "ResourceMapping": {
                    "Source": {"LogicalResourceId": "OpsAlarmsOpsAlertsTopic"}
                },
            }
        ]
        self.assertTrue(refactor.check_refactor_actions(extra, self.moved))


class CommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fake = FakeAws(*templates())
        patcher = mock.patch.object(
            refactor.Aws, "__call__", autospec=True, side_effect=self.fake
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        sleep = mock.patch.object(refactor.time, "sleep")
        sleep.start()
        self.addCleanup(sleep.stop)
        self.work_dir = str(Path(self.tmp.name) / "work")

    def test_preview_then_execute_moves_the_alarms(self) -> None:
        alarms_before = self.fake.alarm_names()
        code, output = run(["preview", "--work-dir", self.work_dir])
        self.assertEqual(code, 0, output)
        self.assertIn("Preview OK: 16 alarm moves", output)
        self.assertNotIn("OpsAlarmsAlarm0", self.fake.templates[NESTED]["Resources"])
        self.assertEqual(len(self.fake.objects), 2)
        create = next(c for c in self.fake.calls if c[1] == "create-stack-refactor")
        self.assertIn("--no-enable-stack-creation", create)
        definitions = json.loads(
            (Path(self.work_dir) / "stack-definitions.json").read_text()
        )
        self.assertTrue(
            definitions[0]["TemplateURL"].startswith(f"https://{BUCKET}.s3.")
        )

        code, output = run(["execute", self.work_dir, "--yes"])
        self.assertEqual(code, 0, output)
        self.assertIn("Done: 16 alarms", output)
        self.assertIn("OpsAlarmsAlarm0", self.fake.templates[NESTED]["Resources"])
        self.assertIn(
            "ManagerRequestDLQAlarm", self.fake.templates[PARENT]["Resources"]
        )
        self.assertEqual(self.fake.alarm_names(), alarms_before)
        self.assertEqual(self.fake.objects, set())

    def test_execute_requires_typed_confirmation(self) -> None:
        self.assertEqual(run(["preview", "--work-dir", self.work_dir])[0], 0)
        with mock.patch("builtins.input", return_value="yes"):
            code, output = run(["execute", self.work_dir])
        self.assertEqual(code, 1)
        self.assertIn("Not confirmed", output)
        self.assertFalse(any(c[1] == "execute-stack-refactor" for c in self.fake.calls))

    def test_preview_stops_before_aws_changes_on_a_bad_template(self) -> None:
        self.fake.templates[PARENT]["Resources"]["OpsAlarmsAlarm0"]["DependsOn"] = "X"
        code, output = run(["preview", "--work-dir", self.work_dir])
        self.assertEqual(code, 1)
        self.assertIn("Refusing to build the refactor", output)
        self.assertFalse(
            any(
                c[1] in ("put-object", "create-stack-refactor") for c in self.fake.calls
            )
        )

    def test_execute_reports_a_failed_execution(self) -> None:
        self.assertEqual(run(["preview", "--work-dir", self.work_dir])[0], 0)
        self.fake.fail_execution = True
        code, output = run(["execute", self.work_dir, "--yes"])
        self.assertEqual(code, 1)
        self.assertIn("EXECUTE_FAILED: boom", output)
        self.assertIn("Do not merge stage 3", output)


if __name__ == "__main__":
    unittest.main()
