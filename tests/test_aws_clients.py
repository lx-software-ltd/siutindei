"""Concurrent callers share one boto3 client.

The admin user list invokes the AWS proxy from several threads. Client
construction is not safe to overlap, so the factory has to serialize the
first build and hand the same client to every waiter.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from app.services import aws_clients


def test_concurrent_get_client_builds_one_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    aws_clients.clear_client_cache()
    created: list[tuple[str, dict[str, Any], object]] = []

    def fake_client(service: str, **kwargs: Any) -> object:
        time.sleep(0.05)
        client = object()
        created.append((service, kwargs, client))
        return client

    monkeypatch.setattr(aws_clients.boto3, "client", fake_client)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(
                lambda _: aws_clients.get_client(
                    "lambda", region_name="ap-southeast-1"
                ),
                range(8),
            )
        )

    assert len(created) == 1
    service, kwargs, client = created[0]
    assert service == "lambda"
    assert kwargs["region_name"] == "ap-southeast-1"
    assert results == [client] * 8
    aws_clients.clear_client_cache()
