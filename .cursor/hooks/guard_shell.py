#!/usr/bin/env python3
"""Block destructive shell commands before Cursor runs them."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

FORCE_PUSH = re.compile(r"(?:^|\s)(?:--force(?:\s|=|$)|--force-with-lease(?:\s|=|$))")
GIT_PUSH = re.compile(r"\bgit\s+push\b", re.IGNORECASE)
SEGMENT_SPLIT = re.compile(r"\s*(?:&&|\|\||[;|\n])\s*")
GIT_RESET_HARD = re.compile(r"\bgit\s+reset\b[^\n]*--hard\b", re.IGNORECASE)
GIT_DELETE = re.compile(r"\bgit\s+(push\b[^\n]*--delete|branch\s+-D)\b", re.IGNORECASE)
RM_RF = re.compile(
    r"\brm\s+(-[a-zA-Z]*[rR][a-zA-Z]*[fF]|-[a-zA-Z]*[fF][a-zA-Z]*[rR])\b"
)
SQL_DESTRUCTIVE = re.compile(
    r"\b(drop\s+table|drop\s+schema|truncate\s+table)\b", re.IGNORECASE
)
CDK_DEPLOY = re.compile(r"\bcdk\s+(deploy|destroy)\b")
AWS_DELETE = re.compile(r"\baws\b[^\n]*\s(delete|terminate)-[a-z0-9-]+")
AMEND = re.compile(r"\bgit\s+commit\b[^\n]*(--amend\b|(^|\s)-[^ \n]*amend)")
ALEMBIC_DOWN = re.compile(r"\balembic\s+(downgrade|stamp)\b", re.IGNORECASE)
PROTECTED_REFS = {"main", "staging", "refs/heads/main", "refs/heads/staging"}


def _segments(command: str) -> list[str]:
    return [part.strip() for part in SEGMENT_SPLIT.split(command) if part.strip()]


def _is_force_push(segment: str) -> bool:
    """True for --force, --force-with-lease, -f, and +refspec pushes."""
    if not GIT_PUSH.search(segment):
        return False
    if FORCE_PUSH.search(segment):
        return True
    for token in segment.split():
        if token.startswith("--"):
            continue
        if token.startswith("-") and "f" in token[1:]:
            return True
        if token.startswith("+") or ":+" in token:
            return True
    return False


def _push_targets_protected(segment: str) -> bool:
    if not GIT_PUSH.search(segment):
        return False
    for token in segment.split():
        if token.startswith("-"):
            continue
        destination = token.split(":")[-1].lstrip("+")
        bare = token.lstrip("+")
        if destination in PROTECTED_REFS and (bare in PROTECTED_REFS or ":" in token):
            return True
    return False


def _deletes_protected_ref(segment: str) -> bool:
    if not GIT_DELETE.search(segment):
        return False
    return any(ref in segment.split() for ref in ("main", "staging"))


def _repo_root() -> Path:
    here = Path.cwd().resolve()
    for candidate in (here, *here.parents):
        if (candidate / ".git").exists():
            return candidate
    return here


def _rm_path_blocked(part: str, root: Path) -> bool:
    if part in {".", "./", "*"}:
        return True
    if not part.startswith("/"):
        pieces = [
            piece
            for piece in part.removeprefix("./").split("/")
            if piece not in {"", "."}
        ]
        return (not pieces) or ".." in pieces or "*" in pieces
    if part in {"/tmp", "/var/tmp"} or part.startswith(("/tmp/", "/var/tmp/")):
        return False
    resolved = Path(part).resolve()
    if resolved == root:
        return True
    try:
        resolved.relative_to(root)
    except ValueError:
        return True
    return False


def _rm_blocked(segment: str) -> bool:
    match = RM_RF.search(segment)
    if not match:
        return False
    remainder = segment[match.end() :].strip()
    if not remainder:
        return True
    paths = [part for part in remainder.split() if not part.startswith("-")]
    if not paths:
        return True
    root = _repo_root()
    return any(_rm_path_blocked(part, root) for part in paths)


def _denied(segment: str) -> tuple[str, str] | None:
    if _is_force_push(segment):
        return (
            "deny",
            "Force-push is blocked. Push a normal fast-forward or open a pull request.",
        )
    if _push_targets_protected(segment):
        return (
            "deny",
            "Pushing to main or staging is blocked. Open a pull request instead.",
        )
    if _deletes_protected_ref(segment):
        return "deny", "Deleting main or staging is blocked."
    if GIT_RESET_HARD.search(segment):
        return "deny", "git reset --hard is blocked."
    if _rm_blocked(segment):
        return "deny", "rm -rf outside the repository or /tmp is blocked."
    if SQL_DESTRUCTIVE.search(segment):
        return (
            "deny",
            "Destructive SQL (DROP TABLE, DROP SCHEMA, TRUNCATE) is blocked.",
        )
    if CDK_DEPLOY.search(segment):
        return (
            "deny",
            "cdk deploy and cdk destroy are blocked. Use the deployment workflow.",
        )
    if AWS_DELETE.search(segment):
        return "deny", "aws delete-* and terminate-* commands are blocked."
    if ALEMBIC_DOWN.search(segment) and "stamp" in segment.lower():
        return "deny", "alembic stamp is blocked in the agent shell."
    return None


def _prompted(segment: str) -> tuple[str, str] | None:
    if AMEND.search(segment):
        return (
            "ask",
            "git commit --amend rewrites history. Confirm this is the commit you just created and have not pushed.",
        )
    if ALEMBIC_DOWN.search(segment):
        return (
            "ask",
            "alembic downgrade rewinds schema. Confirm the target revision and the database.",
        )
    return None


def decide(command: str) -> tuple[str, str]:
    """Return (permission, agent_message). permission is allow, deny, or ask."""
    ask: tuple[str, str] | None = None
    for segment in _segments(command):
        denied = _denied(segment)
        if denied is not None:
            return denied
        prompted = _prompted(segment)
        if prompted is not None and ask is None:
            ask = prompted
    if ask is not None:
        return ask
    return "allow", ""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        print(
            json.dumps(
                {
                    "permission": "deny",
                    "agent_message": "Shell hook received invalid JSON.",
                }
            )
        )
        return 0
    command = str(payload.get("command") or "")
    permission, message = decide(command)
    result: dict[str, str] = {"permission": permission}
    if message:
        result["agent_message"] = message
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
