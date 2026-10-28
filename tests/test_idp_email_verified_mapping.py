"""Social IdPs must pass email_verified through to pre sign-up.

Pre sign-up links a Google or Apple sign-in only when that attribute
is true. Cognito omits it unless the identity provider maps it.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAPPING_FILES = (
    ROOT / "backend/infrastructure/lib/api-stack.ts",
    ROOT / "backend/infrastructure/lib/constructs/auth.ts",
)


def _attribute_mappings(text: str) -> list[str]:
    blocks: list[str] = []
    cursor = 0
    needle = "attributeMapping:"
    while True:
        start = text.find(needle, cursor)
        if start < 0:
            return blocks
        brace = text.find("{", start)
        depth = 0
        for index, char in enumerate(text[brace:], brace):
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    blocks.append(text[brace : index + 1])
                    cursor = index + 1
                    break
        else:
            return blocks


def test_every_social_provider_maps_email_verified() -> None:
    for path in MAPPING_FILES:
        blocks = _attribute_mappings(path.read_text(encoding="utf-8"))
        assert blocks, f"{path} has no attribute mappings"
        for block in blocks:
            assert 'email_verified: "email_verified"' in block, path.name
