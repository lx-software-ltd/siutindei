"""Lambda entrypoint for the AWS / HTTP proxy.

Runs OUTSIDE the VPC so it can reach public AWS API endpoints (e.g.
Cognito with ManagedLogin) and external HTTP APIs that are not
reachable from inside the VPC.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.services.aws_proxy import proxy_handler


def lambda_handler(event: Mapping[str, Any], context: Any) -> dict[str, Any]:
    return proxy_handler(event, context)
