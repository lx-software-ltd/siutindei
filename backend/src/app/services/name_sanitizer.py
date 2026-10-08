"""Deterministic cleanup for organization and activity display names."""

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass

RULE_CODES = (
    "html_entities",
    "nfkc",
    "whitespace",
    "trailing_punctuation",
    "cjk_spacing",
    "title_case",
    "brackets",
    "split_bilingual",
)

_DEFAULT_EXCEPTIONS = (
    "YMCA",
    "HK",
    "LCSD",
    "EDB",
    "SWD",
    "NGO",
    "STEM",
    "AI",
    "IT",
    "UK",
    "US",
    "HKD",
)
_DEFAULT_SUFFIXES = ("lcsd", "edb", "swd")
_ROMAN = re.compile(r"^(?=[IVXLCDM]+$)[IVXLCDM]{1,8}$")
_CJK = re.compile(r"[\u3400-\u9fff]")
_LATIN = re.compile(r"[A-Za-z]")
_TRAILING = " .,;:|/\\-–—·"
_CODE_BRACKETS = re.compile(r"\s*[\(\[][^()\]]*\d[^()\]]*[\)\]]")


@dataclass(frozen=True)
class NameSanitizeConfig:
    """Which cleanup rules run, and the words they leave alone."""

    enabled_rules: frozenset[str]
    exception_words: frozenset[str]
    bracket_suffixes: frozenset[str]

    @staticmethod
    def defaults() -> NameSanitizeConfig:
        return NameSanitizeConfig(
            enabled_rules=frozenset(RULE_CODES),
            exception_words=frozenset(_DEFAULT_EXCEPTIONS),
            bracket_suffixes=frozenset(_DEFAULT_SUFFIXES),
        )


@dataclass(frozen=True)
class NameSanitizeResult:
    """Proposed name plus any Chinese text pulled out of a mixed name."""

    name: str
    original_name: str
    rules: tuple[str, ...]
    translation_patch: dict[str, str]

    @property
    def changed(self) -> bool:
        return self.name != self.original_name or bool(self.translation_patch)


def organization_name_key(name: str) -> str:
    """Fold a name the same way the database trigger does."""
    folded = unicodedata.normalize("NFKC", name or "").casefold()
    compact = re.sub(r"[^\w]+", "", folded, flags=re.UNICODE)
    for suffix in ("有限公司", "limited", "company", "inc", "llc", "ltd"):
        if compact.endswith(suffix) and len(compact) > len(suffix) + 2:
            compact = compact[: -len(suffix)]
            break
    return compact


def sanitize_name(
    name: str,
    translations: dict | None,
    config: NameSanitizeConfig | None = None,
) -> NameSanitizeResult:
    """Return the cleaned name. An empty result keeps the original."""
    settings = config or NameSanitizeConfig.defaults()
    original = name or ""
    text = original
    applied: list[str] = []

    def step(code: str, updated: str) -> None:
        nonlocal text
        if code not in settings.enabled_rules or updated == text:
            return
        text = updated
        applied.append(code)

    if "html_entities" in settings.enabled_rules:
        step("html_entities", html.unescape(text))
    step("nfkc", unicodedata.normalize("NFKC", text))
    step("whitespace", _collapse_whitespace(_space_before_brackets(text)))
    if "whitespace" not in settings.enabled_rules:
        text = _space_before_brackets(text)
    step("trailing_punctuation", _strip_trailing(text))
    step("cjk_spacing", _space_cjk(text))
    step("brackets", _strip_brackets(text, settings.bracket_suffixes))
    text = _space_before_brackets(text)
    step("title_case", _title_case(text, settings.exception_words))
    patch: dict[str, str] = {}
    if "split_bilingual" in settings.enabled_rules:
        split_name, extracted = _split_bilingual(text, translations or {})
        if split_name != text or extracted:
            text = split_name
            patch = extracted
            applied.append("split_bilingual")
    cleaned = _collapse_whitespace(_strip_trailing(_space_before_brackets(text)))
    if not cleaned:
        return NameSanitizeResult(original, original, (), {})
    if cleaned == original and not patch:
        return NameSanitizeResult(original, original, (), {})
    return NameSanitizeResult(cleaned, original, tuple(applied), patch)


def _collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _space_before_brackets(value: str) -> str:
    """Put a space before '(' or '[' when one is missing."""
    return re.sub(r"(?<!\s)([\(\[（［])", r" \1", value)


def _strip_trailing(value: str) -> str:
    return value.strip(_TRAILING)


def _space_cjk(value: str) -> str:
    spaced = re.sub(r"([\u3400-\u9fff])([A-Za-z0-9])", r"\1 \2", value)
    return re.sub(r"([A-Za-z0-9])([\u3400-\u9fff])", r"\1 \2", spaced)


def _strip_brackets(value: str, suffixes: frozenset[str]) -> str:
    updated = value
    if suffixes:
        alt = "|".join(
            re.escape(item) for item in sorted(suffixes, key=len, reverse=True)
        )
        pattern = re.compile(rf"\s*[\(\[]\s*(?:{alt})\s*[\)\]]", re.IGNORECASE)
        updated = pattern.sub(" ", updated)
    updated = _CODE_BRACKETS.sub(" ", updated)
    return _collapse_whitespace(updated)


def _title_case(value: str, exceptions: frozenset[str]) -> str:
    return " ".join(_title_token(token, exceptions) for token in value.split(" "))


def _title_token(token: str, exceptions: frozenset[str]) -> str:
    letters = re.sub(r"[^A-Za-z]", "", token)
    if len(letters) < 2 or not letters.isupper():
        return token
    match = re.match(r"^([^A-Za-z0-9]*)(.*?)([^A-Za-z0-9]*)$", token)
    if match is None:
        return token
    prefix, core, suffix = match.groups()
    upper = core.upper()
    if upper in exceptions or _ROMAN.match(upper):
        return token
    pieces = re.split(r"(-)", core)
    titled = "".join(piece.capitalize() if piece != "-" else piece for piece in pieces)
    return f"{prefix}{titled}{suffix}"


def _split_bilingual(value: str, translations: dict) -> tuple[str, dict[str, str]]:
    if not _CJK.search(value) or not _LATIN.search(value):
        return value, {}
    chinese = "".join(char for char in value if _CJK.match(char))
    english = _collapse_whitespace(
        "".join(char if not _CJK.match(char) else " " for char in value)
    )
    if len(chinese) < 2 or len(english) < 2:
        return value, {}
    existing = ""
    if isinstance(translations, dict):
        existing = str(translations.get("zh") or "").strip()
    patch: dict[str, str] = {}
    if not existing:
        patch["zh"] = chinese
    return english, patch
