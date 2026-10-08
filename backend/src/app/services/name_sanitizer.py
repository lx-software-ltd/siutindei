"""Deterministic cleanup for organization and activity display names."""

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass

from app.services.name_sanitizer_areas import HK_AREAS

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
# Always kept in capitals, even when the saved settings list omits them.
_BUILTIN_EXCEPTIONS = frozenset(
    {
        "CCC",
        "ELCHK",
        "HHCKLA",
        "HKSKH",
        "HKU",
        "HKUST",
        "SKH",
        "TWGHS",
        "UPC",
        "YWCA",
    }
)
_DEFAULT_SUFFIXES = ("lcsd", "edb", "swd")
_ROMAN_NUMERALS = frozenset(
    {
        "I",
        "II",
        "III",
        "IV",
        "V",
        "VI",
        "VII",
        "VIII",
        "IX",
        "X",
        "XI",
        "XII",
        "XIII",
        "XIV",
        "XV",
        "XVI",
        "XVII",
        "XVIII",
        "XIX",
        "XX",
    }
)
_CJK = re.compile(r"[\u3400-\u9fff]")
_LATIN = re.compile(r"[A-Za-z]")
_TRAILING = " .,;:|/\\-–—·"
_CODE_BRACKETS = re.compile(r"\s*[\(\[][^()\]]*\d[^()\]]*[\)\]]")
_BRACKET_PAIRS = (("(", ")"), ("[", "]"), ("（", "）"), ("［", "］"))
_DOTTED_INITIALISM = re.compile(r"^[A-Za-z](?:\.[A-Za-z])+\.?$")
_BRANCH_SUFFIX = re.compile(r"(分店|分校|店)$")
_SMALL_WORDS = frozenset(
    {
        "A",
        "AN",
        "THE",
        "AND",
        "NOR",
        "BUT",
        "AS",
        "AT",
        "BY",
        "FOR",
        "FROM",
        "IN",
        "INTO",
        "OF",
        "OFF",
        "ONTO",
        "OUT",
        "OVER",
        "UP",
        "WITH",
    }
)
_PHRASE_END = frozenset(":.;!?")
_OPEN_BRACKET = re.compile(r"^[\(\[（［]")


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
    """Trim trailing punctuation, but keep a dotted initialism period."""
    text = value
    while text and text[-1] in _TRAILING:
        if text[-1] == ".":
            last_word = text.split()[-1] if text.split() else ""
            if _DOTTED_INITIALISM.match(last_word):
                break
        text = text[:-1]
    return text


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


def _kept_exceptions(exceptions: frozenset[str]) -> frozenset[str]:
    return frozenset(item.upper() for item in exceptions) | _BUILTIN_EXCEPTIONS


def _title_case(value: str, exceptions: frozenset[str]) -> str:
    kept = _kept_exceptions(exceptions)
    words = value.split(" ")
    titled: list[str] = []
    phrase_start = True
    for word in words:
        if not word:
            titled.append(word)
            continue
        start = phrase_start or bool(_OPEN_BRACKET.match(word))
        titled.append(_title_word(word, kept, start))
        phrase_start = word[-1] in _PHRASE_END
    return " ".join(titled)


def _is_dotted_initialism(token: str) -> bool:
    return bool(_DOTTED_INITIALISM.match(token))


def _title_word(word: str, exceptions: frozenset[str], phrase_start: bool) -> str:
    letters = re.sub(r"[^A-Za-z]", "", word)
    if len(letters) < 2 or not letters.isupper():
        return word
    match = re.match(r"^([^A-Za-z0-9]*)(.*?)([^A-Za-z0-9]*)$", word)
    if match is None:
        return word
    prefix, core, suffix = match.groups()
    upper = core.upper()
    letters_upper = letters.upper()
    if (
        upper in exceptions
        or letters_upper in exceptions
        or upper in _ROMAN_NUMERALS
        or _is_dotted_initialism(core)
        or _is_dotted_initialism(word)
    ):
        return word
    if not phrase_start and upper in _SMALL_WORDS:
        return f"{prefix}{core.lower()}{suffix}"
    pieces = re.split(r"(-)", core)
    titled: list[str] = []
    piece_start = True
    for piece in pieces:
        if piece == "-":
            titled.append(piece)
            continue
        piece_upper = piece.upper()
        if piece_upper in exceptions or piece_upper in _ROMAN_NUMERALS:
            titled.append(piece)
            piece_start = False
            continue
        if not piece_start and piece_upper in _SMALL_WORDS:
            titled.append(piece.lower())
        else:
            titled.append(piece.capitalize())
        piece_start = False
    return f"{prefix}{''.join(titled)}{suffix}"


def _cjk_only(value: str) -> str:
    return "".join(char for char in value if _CJK.match(char))


def _is_place_or_branch(inner: str) -> bool:
    compact = _cjk_only(inner)
    if not compact:
        return False
    if _BRANCH_SUFFIX.search(compact):
        return True
    return compact in HK_AREAS


def _starts_with_cjk(value: str) -> bool:
    stripped = value.lstrip()
    return bool(stripped) and bool(_CJK.match(stripped[0]))


def _should_keep_mixed(original: str, english: str, chinese: str) -> bool:
    if _BRANCH_SUFFIX.search(chinese):
        return True
    if _starts_with_cjk(original) and len(chinese) >= 6 and len(english.split()) <= 2:
        return True
    return False


def _restore_place_brackets(original: str, english: str) -> str:
    restored = english
    for opener, closer in _BRACKET_PAIRS:
        pattern = re.compile(
            re.escape(opener)
            + r"([^"
            + re.escape(opener + closer)
            + r"]*)"
            + re.escape(closer)
        )
        for match in pattern.finditer(original):
            inner = match.group(1).strip()
            if not _is_place_or_branch(inner):
                continue
            token = f"{opener}{inner}{closer}"
            if token not in restored:
                restored = f"{restored} {token}"
    return _collapse_whitespace(restored)


def _split_bilingual(value: str, translations: dict) -> tuple[str, dict[str, str]]:
    if not _CJK.search(value) or not _LATIN.search(value):
        return value, {}
    chinese = _cjk_only(value)
    english = _tidy_split_brackets(
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
    if _should_keep_mixed(value, english, chinese):
        return value, patch
    english = _restore_place_brackets(value, english)
    if len(english) < 2:
        return value, patch
    return english, patch


def _tidy_split_brackets(value: str) -> str:
    """Remove brackets emptied by pulling Chinese into translations."""
    updated = value
    for opener, closer in _BRACKET_PAIRS:
        pattern = re.compile(
            re.escape(opener)
            + r"([^"
            + re.escape(opener + closer)
            + r"]*)"
            + re.escape(closer)
        )

        def _replace(
            match: re.Match[str],
            *,
            open_b: str = opener,
            close_b: str = closer,
        ) -> str:
            inner = match.group(1).strip()
            if not inner:
                return ""
            return f"{open_b}{inner}{close_b}"

        updated = pattern.sub(_replace, updated)
    return _collapse_whitespace(updated)
