"""Record model and geocoder replies and reuse them for the same input."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.engine import get_engine
from app.db.models import LookupAnswer, ModelAnswer
from app.services.data_quality.fingerprint import fingerprint


def cached_chat_completion(**kwargs: Any) -> str:
    """Return the recorded model body, or call OpenRouter and store it.

    ``refresh=True`` skips the recorded reply. ``session`` keeps the write
    in the caller's transaction. Without it, the reply is committed on
    its own so a later run can reuse it.
    """
    refresh = bool(kwargs.pop("refresh", False))
    prompt_version = str(kwargs.pop("prompt_version", "unversioned"))
    session = kwargs.pop("session", None)
    model = str(kwargs.get("model") or "")
    key = fingerprint(
        {
            "prompt_version": prompt_version,
            "model": model,
            "system": kwargs.get("system_prompt") or "",
            "user": kwargs.get("user_content") or "",
            "temperature": kwargs.get("temperature", 0),
        }
    )
    if not refresh:
        cached = _read_model_body(session, key)
        if cached is not None:
            return cached
    from app.services.openrouter_client import openrouter_chat_completion

    body = openrouter_chat_completion(**kwargs)
    _write_model(session, key, model, prompt_version, body)
    return body


def lookup_key(provider: str, query: str) -> str:
    """Hash a geocoder provider and the query text."""
    return fingerprint({"provider": provider, "query": query.strip()})


def load_lookup_answer(
    session: Session,
    provider: str,
    query: str,
) -> dict[str, Any] | None:
    """Return the first recorded reply for this query, if one exists."""
    row = session.get(LookupAnswer, lookup_key(provider, query))
    if row is None or not isinstance(row.response, dict):
        return None
    return row.response


def store_lookup_answer(
    session: Session,
    provider: str,
    query: str,
    response: dict[str, Any],
    *,
    refresh: bool = False,
) -> None:
    """Store a geocoder reply. The first reply stays unless refresh is set."""
    key = lookup_key(provider, query)
    existing = session.get(LookupAnswer, key)
    if existing is not None and not refresh:
        return
    if existing is None:
        session.add(
            LookupAnswer(
                key_hash=key,
                provider=provider,
                query=query.strip(),
                response=response,
            )
        )
        return
    existing.response = response
    existing.provider = provider
    existing.query = query.strip()


def _read_model_body(session: Session | None, key: str) -> str | None:
    if session is not None:
        return _body(session.get(ModelAnswer, key))
    with Session(get_engine()) as bound:
        return _body(bound.get(ModelAnswer, key))


def _body(row: ModelAnswer | None) -> str | None:
    if row is None or not isinstance(row.response, dict):
        return None
    body = row.response.get("body")
    if not isinstance(body, str):
        return None
    return body


def _write_model(
    session: Session | None,
    key: str,
    model: str,
    prompt_version: str,
    body: str,
) -> None:
    own = session is None
    bound = session
    if bound is None:
        bound = Session(get_engine())
    try:
        existing = bound.get(ModelAnswer, key)
        if existing is None:
            bound.add(
                ModelAnswer(
                    key_hash=key,
                    model=model,
                    prompt_version=prompt_version,
                    response={"body": body},
                )
            )
        else:
            existing.response = {"body": body}
            existing.model = model
            existing.prompt_version = prompt_version
        if own:
            bound.commit()
        else:
            bound.flush()
    finally:
        if own:
            bound.close()
