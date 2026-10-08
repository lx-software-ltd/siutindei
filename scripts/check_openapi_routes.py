#!/usr/bin/env python3
"""Require explicit API Gateway paths to appear in docs/api/*.yaml.

Greedy ``{proxy+}`` resources are skipped. Path parameters are compared
with the parameter name erased, so ``{id}`` matches ``{organizationId}``.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STACK = ROOT / "backend" / "infrastructure" / "lib" / "api-stack.ts"
API_DOCS = ROOT / "docs" / "api"

ARRAY_RE = re.compile(r"const\s+(\w+)\s*=\s*\[(.*?)\]", re.DOTALL)
STRING_RE = re.compile(r'"([^"]+)"')
ADD_RE = re.compile(
    r"const\s+(\w+)\s*=\s*([\w.]+)\.addResource\(\s*(?:\"([^\"]+)\"|(\w+))\s*\)"
)
FOR_RE = re.compile(r"for\s*\(\s*const\s+(\w+)\s+of\s+(\w+)\s*\)")
IF_EQ_RE = re.compile(r'if\s*\(\s*\w+\s*===\s*"([^"]+)"\s*\)')
METHOD_RE = re.compile(r"(\w+)\.addMethod\(")
PARAM_RE = re.compile(r"\{[^}]+\}")


def _arrays(text: str) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for match in ARRAY_RE.finditer(text):
        values = STRING_RE.findall(match.group(2))
        if values:
            found[match.group(1)] = values
    return found


def _join(base: str, segment: str) -> str:
    segment = segment.removeprefix("/")
    if not base:
        return f"/{segment}"
    return f"{base.rstrip('/')}/{segment}"


def _normalize(path: str) -> str:
    return PARAM_RE.sub("{}", path)


def gateway_paths(text: str) -> list[str]:
    """Return concrete paths that have an addMethod call."""
    arrays = _arrays(text)
    nodes: dict[str, set[str]] = {"api.root": {""}}
    loops: list[tuple[int, str, str]] = []
    filters: list[tuple[int, str]] = []
    required: list[str] = []
    depth = 0
    for line in text.splitlines():
        depth += line.count("{") - line.count("}")
        loop_match = FOR_RE.search(line)
        if loop_match:
            loops.append((depth, loop_match.group(1), loop_match.group(2)))
        if_match = IF_EQ_RE.search(line)
        if if_match:
            filters.append((depth, f"/{if_match.group(1)}/"))
        loops = [item for item in loops if item[0] <= depth]
        filters = [item for item in filters if item[0] <= depth]
        bindings = {name: arrays.get(source, []) for _, name, source in loops}
        add_match = ADD_RE.search(line)
        if add_match:
            name, parent, literal, variable = add_match.groups()
            bases = nodes.get(parent, set())
            if filters:
                bases = {
                    base
                    for base in bases
                    if all(token in f"{base}/" for _, token in filters)
                }
            segments: list[str] = []
            if literal is not None:
                segments = [literal]
            elif bindings.get(variable):
                segments = bindings[variable]
            elif variable in arrays:
                segments = arrays[variable]
            built = {_join(base, segment) for base in bases for segment in segments}
            nodes[name] = built
        method_match = METHOD_RE.search(line)
        if method_match:
            required.extend(sorted(nodes.get(method_match.group(1), set())))
    return required


def documented_paths() -> set[str]:
    found: set[str] = set()
    for path in API_DOCS.glob("*.yaml"):
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("/") and stripped.endswith(":"):
                found.add(_normalize(stripped[:-1].strip()))
    return found


def missing_paths(stack_text: str, docs: set[str]) -> list[str]:
    missing: list[str] = []
    seen: set[str] = set()
    for path in gateway_paths(stack_text):
        if "{proxy+}" in path or path in seen:
            continue
        seen.add(path)
        if _normalize(path) not in docs:
            missing.append(path)
    return missing


def main() -> int:
    if not STACK.exists():
        print(f"Missing {STACK}", file=sys.stderr)
        return 1
    missing = missing_paths(
        STACK.read_text(encoding="utf-8"),
        documented_paths(),
    )
    if missing:
        print("OpenAPI route check failed:", file=sys.stderr)
        for path in missing:
            print(f"- {path} is not in docs/api/*.yaml", file=sys.stderr)
        return 1
    print("OpenAPI route check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
