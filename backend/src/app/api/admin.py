"""Admin CRUD API handlers.

Special cases and generic CRUD are a route table in ``admin_routes``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.api.admin_auth import _is_admin, _is_importer
from app.api.admin_enrichment import organization_tail
from app.api.admin_request import _parse_path
from app.api.admin_routes import (
    dispatch_admin,
    handle_manager_routes,
    handle_user_routes,
)
from app.api.partner_routes import handle_partner_routes as _handle_partner_routes
from app.exceptions import ValidationError
from app.utils import json_response
from app.utils.logging import configure_logging, get_logger, set_request_context
from app.utils.responses import validate_content_type

configure_logging()
logger = get_logger(__name__)


def _handle_crud(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """CRUD entry kept on this module so tests can patch it."""
    from app.api.admin_crud import _handle_crud as impl

    return impl(*args, **kwargs)


def _handle_admin_imports(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Import entry kept on this module so tests can patch it."""
    from app.api.admin_imports import _handle_admin_imports as impl

    return impl(*args, **kwargs)


def handle_org_enrichment(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Enrichment entry kept on this module so tests can patch it."""
    from app.api.admin_enrichment import handle_org_enrichment as impl

    return impl(*args, **kwargs)


def lambda_handler(event: Mapping[str, Any], context: Any) -> dict[str, Any]:
    """Handle admin CRUD requests."""
    request_id = event.get("requestContext", {}).get("requestId", "")
    set_request_context(req_id=request_id)

    method = event.get("httpMethod", "")
    path = event.get("path", "")
    base_path, resource, resource_id, sub_resource = _parse_path(path)

    try:
        validate_content_type(event)
    except ValidationError as exc:
        logger.warning(f"Content-Type validation failed: {exc.message}")
        return json_response(exc.status_code, exc.to_dict(), event=event)

    logger.info(
        f"Admin request: {method} {path}",
        extra={
            "base_path": base_path,
            "resource": resource,
            "resource_id": resource_id,
        },
    )

    if base_path == "user":
        return handle_user_routes(event, method, resource, resource_id)
    if base_path == "manager":
        return handle_manager_routes(event, method, resource, resource_id)
    if base_path == "partner":
        return _handle_partner_routes(event, method, resource, resource_id)
    if base_path != "admin":
        return json_response(404, {"error": "Not found"}, event=event)
    if not _is_admin(event) and not _importer_can_access(
        event,
        method,
        resource,
        resource_id,
    ):
        logger.warning("Unauthorized admin access attempt")
        return json_response(403, {"error": "Forbidden"}, event=event)
    return dispatch_admin(event, method, resource, resource_id, sub_resource)


def _importer_can_access(
    event: Mapping[str, Any],
    method: str,
    resource: str,
    resource_id: str | None,
) -> bool:
    """Allow importer JWTs on catalog import and owner-UI listing routes."""
    if not _is_importer(event):
        return False
    if resource == "imports":
        if method == "POST" and resource_id in (None, "presign"):
            return True
        return bool(method == "GET" and resource_id and resource_id != "export")
    if resource == "organizations":
        tail = organization_tail(str(event.get("path") or ""))
        if tail == ["enrichment"] and method in {"GET", "POST"}:
            return True
        if method == "GET":
            return True
        return bool(method == "PATCH" and resource_id)
    return False
