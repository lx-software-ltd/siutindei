"""Record model replies for data-quality runs and reuse the first good one."""

from __future__ import annotations

import json
from typing import Any, Callable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.engine import get_engine
from app.db.models import DataQualityRun, LookupAnswer, ModelAnswer
from app.services.data_quality.fingerprint import fingerprint
from app.services.openrouter_client import usage_from_body

CATEGORY_PROMPT_VERSION = "verify-1"
LOCATION_PROMPT_VERSION = "locations-1"
TRANSLATION_PROMPT_VERSION = "translations-1"


class ModelReply:
    """A model body. ``keep`` stores it after the caller has parsed it."""

    def __init__(
        self,
        body: str,
        usage: dict[str, Any],
        *,
        store: bool,
        refresh: bool,
        key: str | None,
        model: str,
        prompt_version: str,
    ) -> None:
        self.body = body
        self.usage = usage
        self.store = store
        self.refresh = refresh
        self.key = key
        self.model = model
        self.prompt_version = prompt_version

    def keep(self, session: Session) -> None:
        """Store a parsed reply. The first reply stays unless refresh is set."""
        if not self.store or self.key is None:
            return
        try:
            with session.begin_nested():
                existing = session.get(ModelAnswer, self.key)
                if existing is None:
                    session.add(
                        ModelAnswer(
                            key_hash=self.key,
                            model=self.model,
                            prompt_version=self.prompt_version,
                            response={"body": self.body},
                        )
                    )
                elif self.refresh:
                    existing.response = {"body": self.body}
                    existing.model = self.model
                    existing.prompt_version = self.prompt_version
                session.flush()
        except IntegrityError:
            return


def recording_flags(session: Session, data_quality_run_id) -> tuple[bool, bool]:
    """Return whether this scan should record replies, and whether to refresh."""
    if data_quality_run_id is None:
        return False, False
    parent = session.get(DataQualityRun, data_quality_run_id)
    if parent is None:
        return True, False
    return True, bool(parent.refresh)


def recorded_completion(
    *,
    record: bool,
    refresh: bool,
    prompt_version: str,
    model: str,
    system_prompt: str,
    user_content: str,
    invoke: Callable[[], str],
    temperature: float = 0,
) -> ModelReply:
    """Call the model, or reuse the recorded reply for this prompt.

    A recorded hit has empty usage so it is not charged again. The live
    reply is stored only when the caller invokes ``keep`` after parsing.
    """
    key = fingerprint(
        {
            "prompt_version": prompt_version,
            "model": model,
            "system": system_prompt,
            "user": user_content,
            "temperature": temperature,
        }
    )
    if record and not refresh:
        cached = _read_body(key)
        if cached is not None:
            return ModelReply(
                _without_usage(cached),
                {},
                store=False,
                refresh=False,
                key=key,
                model=model,
                prompt_version=prompt_version,
            )
    body = invoke()
    return ModelReply(
        body,
        usage_from_body(body),
        store=record,
        refresh=refresh,
        key=key,
        model=model,
        prompt_version=prompt_version,
    )


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


def _read_body(key: str) -> str | None:
    with Session(get_engine()) as session:
        row = session.get(ModelAnswer, key)
        if row is None or not isinstance(row.response, dict):
            return None
        body = row.response.get("body")
        if not isinstance(body, str):
            return None
        return body


def _without_usage(body: str) -> str:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return body
    if not isinstance(payload, dict) or "usage" not in payload:
        return body
    stripped = dict(payload)
    stripped["usage"] = {}
    return json.dumps(stripped)
