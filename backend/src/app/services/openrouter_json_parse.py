"""Parse JSON from OpenRouter assistant text, with one repair retry."""

from __future__ import annotations

import json
import re
from typing import Any

from app.services.openrouter_client import (
    WORKLOAD_JSON_REPAIR,
    OpenRouterError,
    extract_message_text,
    openrouter_chat_completion,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)

JSON_SNIPPET_RADIUS = 80
DEFAULT_JSON_REPAIR_TIMEOUT_SECONDS = 60
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def prepare_openrouter_json_text(text: str) -> str:
    """Strip markdown fences and surrounding whitespace."""
    cleaned = text.strip()
    fence = _JSON_FENCE_RE.search(cleaned)
    if fence:
        cleaned = fence.group(1).strip()
    return cleaned


def openrouter_json_text_candidates(text: str) -> list[str]:
    """Return ordered JSON substrings to try before a repair call."""
    cleaned = prepare_openrouter_json_text(text)
    candidates = [cleaned]
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        sliced = cleaned[start : end + 1]
        if sliced not in candidates:
            candidates.append(sliced)
    return candidates


def loads_openrouter_json(
    text: str,
    *,
    context: str,
    timeout: int = DEFAULT_JSON_REPAIR_TIMEOUT_SECONDS,
    workload: str = WORKLOAD_JSON_REPAIR,
) -> Any:
    """Parse JSON from assistant text, repairing once on failure."""
    cleaned = prepare_openrouter_json_text(text)
    if "{" not in cleaned:
        raise OpenRouterError(f"Model returned no JSON object for {context}")
    last_error: json.JSONDecodeError | None = None
    repair_source = cleaned
    for candidate in openrouter_json_text_candidates(text):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc
            repair_source = candidate
    if last_error is None:
        raise OpenRouterError(f"No JSON object found for {context}")
    logger.warning(
        "OpenRouter JSON parse failed; attempting repair",
        extra={"context": context, "error": str(last_error)},
    )
    try:
        repaired_body = openrouter_chat_completion(
            system_prompt=(
                "You repair malformed JSON documents and return strict JSON only."
            ),
            user_content=(
                "The following text was supposed to be one JSON object but "
                f"failed to parse: {last_error}. Return the same data as "
                "strict JSON only. Do not add commentary.\n\n"
                f"{repair_source}"
            ),
            timeout=timeout,
            workload=workload,
            temperature=0,
            max_attempts=1,
        )
        repaired = extract_message_text(repaired_body)
    except OpenRouterError as exc:
        raise OpenRouterError(
            f"Parser returned invalid JSON for {context}: {last_error}"
        ) from exc
    for candidate in openrouter_json_text_candidates(repaired):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    raise OpenRouterError(
        f"Parser returned invalid JSON for {context} even after repair"
    )
