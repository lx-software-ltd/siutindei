"""Harness checks stay green and the shell guard denies destructive commands."""

from __future__ import annotations

import importlib.util
import io
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Completed:
    def __init__(self, stdout: str, returncode: int = 0) -> None:
        self.stdout = stdout
        self.stderr = ""
        self.returncode = returncode


def test_missing_pre_commit_returns_one_followup(monkeypatch) -> None:
    stop = _load("stop_gate", ROOT / ".cursor" / "hooks" / "stop_gate.py")

    def fake_run(command, **kwargs):
        if command[0] == "git":
            return _Completed(" M file.py\n")
        if command[0] in {stop.sys.executable, "node"}:
            return _Completed("", 0)
        raise FileNotFoundError(command[0])

    monkeypatch.setattr(stop.subprocess, "run", fake_run)
    monkeypatch.setattr(stop.sys, "stdin", io.StringIO(json.dumps({"status": "completed"})))
    stdout = io.StringIO()
    monkeypatch.setattr(stop.sys, "stdout", stdout)
    assert stop.main() == 0
    message = json.loads(stdout.getvalue())["followup_message"]
    assert message.count("pre-commit is not on PATH") == 1
    assert "lx-software-ltd/actions" in message
    assert "network" in message
    assert "clone that repository" in message


def test_pre_commit_failure_does_not_say_the_tool_is_missing(monkeypatch) -> None:
    stop = _load("stop_gate", ROOT / ".cursor" / "hooks" / "stop_gate.py")

    def fake_run(command, **kwargs):
        if command[0] == "git":
            return _Completed(" M file.py\n")
        if command[0] == "pre-commit":
            return _Completed("hook failed", 1)
        return _Completed("", 0)

    monkeypatch.setattr(stop.subprocess, "run", fake_run)
    monkeypatch.setattr(stop.sys, "stdin", io.StringIO(json.dumps({"status": "completed"})))
    stdout = io.StringIO()
    monkeypatch.setattr(stop.sys, "stdout", stdout)
    assert stop.main() == 0
    message = json.loads(stdout.getvalue())["followup_message"]
    assert "hook failed" in message
    assert "pre-commit is not on PATH" not in message


def test_shell_guard_decisions() -> None:
    module = _load("guard_shell", ROOT / ".cursor" / "hooks" / "guard_shell.py")
    denied = [
        "git push --force origin feature",
        "git push --force-with-lease origin cursor/x",
        "git push origin +main",
        "git push origin +feature",
        "git push origin HEAD:+main",
        "git push -uf origin feature",
        "git push origin main",
        "git push origin HEAD:staging",
        "git reset --hard HEAD",
        "rm -rf /workspace",
        "rm -rf ../outside",
        "psql -c 'DROP TABLE users'",
        "npx cdk deploy",
        "aws s3 delete-bucket --bucket example",
        "alembic stamp head",
        "git branch -D main",
    ]
    for command in denied:
        permission, _message = module.decide(command)
        assert permission == "deny", command
    permission, _message = module.decide("git commit --amend")
    assert permission == "ask"
    permission, _message = module.decide("alembic downgrade -1")
    assert permission == "ask"
    permission, _message = module.decide("pytest tests/test_board_policy.py")
    assert permission == "allow"
    permission, _message = module.decide("rm -rf /tmp/cursor-scratch")
    assert permission == "allow"
    permission, _message = module.decide("rm -rf node_modules")
    assert permission == "allow"
    permission, _message = module.decide("rm -rf apps/admin_web/.next")
    assert permission == "allow"
    permission, message = module.decide("rm -f out.txt && git push origin feature")
    assert permission == "allow", message


def test_session_start_writes_marker(tmp_path: Path) -> None:
    module = _load("session_start", ROOT / ".cursor" / "hooks" / "session_start.py")
    marker = tmp_path / "marker"
    previous = os.environ.get("CURSOR_HOOK_MARKER")
    os.environ["CURSOR_HOOK_MARKER"] = str(marker)
    try:
        assert module.main() == 0
    finally:
        if previous is None:
            os.environ.pop("CURSOR_HOOK_MARKER", None)
        else:
            os.environ["CURSOR_HOOK_MARKER"] = previous
    assert marker.read_text(encoding="utf-8") == "sessionStart\n"


def test_openapi_parser_limits_media_to_organizations() -> None:
    module = _load("check_openapi_routes", ROOT / "scripts" / "check_openapi_routes.py")
    stack = (ROOT / "backend" / "infrastructure" / "lib" / "api-stack.ts").read_text(
        encoding="utf-8"
    )
    paths = set(module.gateway_paths(stack))
    assert "/v1/admin/organizations/{id}/media" in paths
    assert "/v1/admin/locations/{id}/media" not in paths
    assert module.missing_paths(stack, module.documented_paths()) == []


def test_board_pr_body_uses_the_template() -> None:
    module = _load("board_pr_body", ROOT / "scripts" / "ci" / "board_pr_body.py")
    body = module.render(
        brief="Fix the empty state.\n",
        zone="open",
        evidence="40 passed",
        task_id="task-1",
    )
    assert body.startswith("## Intent\n")
    assert "## Zone\n\nopen\n" in body
    assert "40 passed" in body
    assert body.rstrip().endswith("Task: task-1")
