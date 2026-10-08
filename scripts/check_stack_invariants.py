#!/usr/bin/env python3
"""Scan CDK sources for constraints the typechecker does not enforce."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "backend" / "infrastructure" / "lib"
SECRET_ID = re.compile(r"(Secret|Password|ApiKey)")
CFN_PARAMETER = re.compile(r"new\s+(?:cdk\.)?CfnParameter\(")
BUCKET_NAME = re.compile(r"bucketName:\s*[`'\"]([^`'\"]+)[`'\"]")
SECRET_NAME = re.compile(r"secretName:\s*([^\n,]+)")
BUCKET_LIMIT = 63


def _balanced_end(text: str, start: int) -> int:
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
    return len(text)


def _strip_comments(text: str) -> str:
    without_block = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"//.*?$", "", without_block, flags=re.MULTILINE)


def check(text: str, rel: str) -> list[str]:
    errors: list[str] = []
    code = _strip_comments(text)
    if "Cors.ALL_ORIGINS" in code:
        errors.append(f"{rel}: Cors.ALL_ORIGINS is not allowed")
    for match in CFN_PARAMETER.finditer(text):
        end = _balanced_end(text, match.start())
        block = text[match.start() : end]
        ident = re.search(r'CfnParameter\(\s*this\s*,\s*"([^"]+)"', block)
        name = ident.group(1) if ident else ""
        if not SECRET_ID.search(name):
            continue
        if "noEcho: true" not in block and "noEcho:true" not in block:
            errors.append(f"{rel}: secret parameter {name} is missing noEcho")
    for match in BUCKET_NAME.finditer(code):
        literal = match.group(1)
        if "${" in literal:
            continue
        if len(literal) > BUCKET_LIMIT:
            errors.append(
                f"{rel}: bucket name is {len(literal)} characters (max {BUCKET_LIMIT})"
            )
    for match in SECRET_NAME.finditer(code):
        value = match.group(1).strip()
        if value.startswith("name("):
            continue
        if value.startswith(("`", '"', "'")):
            errors.append(f"{rel}: secretName must use the name() helper ({value})")
    return errors


def main() -> int:
    errors: list[str] = []
    for path in sorted(LIB.rglob("*.ts")):
        rel = path.relative_to(ROOT).as_posix()
        errors.extend(check(path.read_text(encoding="utf-8"), rel))
    if errors:
        print("Stack invariant check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Stack invariant check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
