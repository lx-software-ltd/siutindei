"""OpenRouter: room for the reply (output cap and reasoning off)."""

from __future__ import annotations

import json

import pytest
from app.services import openrouter_client
from app.services.openrouter_client import OpenRouterError


@pytest.fixture
def sent(monkeypatch) -> list[dict[str, object]]:
    bodies: list[dict[str, object]] = []

    def fake_invoke(**kwargs: object) -> dict[str, object]:
        bodies.append(json.loads(str(kwargs["body"])))
        return {"status": 200, "body": '{"choices": []}'}

    monkeypatch.setenv("OPENROUTER_CHAT_COMPLETIONS_URL", "https://openrouter.test/v1")
    monkeypatch.setattr(openrouter_client, "http_invoke", fake_invoke)
    monkeypatch.setattr(openrouter_client, "get_openrouter_api_key", lambda: "test")
    return bodies


def _call(**kwargs: object) -> None:
    openrouter_client.openrouter_chat_completion(
        system_prompt="s",
        user_content="u",
        timeout=5,
        workload="test",
        model="test/model",
        fallback_models=[],
        deny_data_collection=False,
        **kwargs,  # type: ignore[arg-type]
    )


def test_other_workloads_send_no_output_cap_or_reasoning(sent) -> None:
    _call()
    assert "max_tokens" not in sent[0]
    assert "reasoning" not in sent[0]


def test_output_cap_and_reasoning_off_are_sent_when_asked(sent) -> None:
    _call(max_tokens=12_000, reasoning_off=True)
    assert sent[0]["max_tokens"] == 12_000
    assert sent[0]["reasoning"] == {"enabled": False}


def _reply_body() -> str:
    return json.dumps(
        {
            "model": "test/model",
            "choices": [{"finish_reason": "stop", "message": {"content": "{}"}}],
        }
    )


def test_enrichment_asks_for_reply_room(monkeypatch) -> None:
    from app.services.enrichment import run as run_module
    from app.services.enrichment.constants import MAX_REPLY_TOKENS

    calls: list[dict[str, object]] = []

    def fake_completion(**kwargs: object) -> str:
        calls.append(kwargs)
        return _reply_body()

    monkeypatch.setattr(
        "app.services.openrouter_client.openrouter_chat_completion", fake_completion
    )
    run_module._model("page text")

    assert calls[0]["max_tokens"] == MAX_REPLY_TOKENS
    assert calls[0]["reasoning_off"] is True


def test_enrichment_retries_plainly_when_the_model_refuses_the_settings(
    monkeypatch,
) -> None:
    from app.services.enrichment import run as run_module

    calls: list[dict[str, object]] = []

    def fake_completion(**kwargs: object) -> str:
        calls.append(kwargs)
        if kwargs.get("reasoning_off"):
            raise OpenRouterError("reasoning is mandatory", status=400)
        return _reply_body()

    monkeypatch.setattr(
        "app.services.openrouter_client.openrouter_chat_completion", fake_completion
    )
    run_module._model("page text")

    assert len(calls) == 2
    assert "max_tokens" not in calls[1] and "reasoning_off" not in calls[1]


def test_enrichment_does_not_retry_other_failures(monkeypatch) -> None:
    from app.services.enrichment import run as run_module

    calls: list[dict[str, object]] = []

    def fake_completion(**kwargs: object) -> str:
        calls.append(kwargs)
        raise OpenRouterError("server error", status=502)

    monkeypatch.setattr(
        "app.services.openrouter_client.openrouter_chat_completion", fake_completion
    )
    with pytest.raises(OpenRouterError):
        run_module._model("page text")
    assert len(calls) == 1
