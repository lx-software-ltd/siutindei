"""Admin CRUD API handlers.

This module provides admin CRUD operations using the repository pattern
for cleaner separation of concerns and better testability.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from app.api.admin_address_search import _handle_address_search
from app.api.admin_areas import (
    _handle_list_activity_categories,
    _handle_list_areas,
    _handle_toggle_area,
)
from app.api.admin_api_keys import _handle_admin_api_keys
from app.api.admin_audit import _handle_audit_logs
from app.api.admin_auth import (
    _get_managed_organization_ids,
    _is_admin,
    _is_importer,
    _is_manager,
)
from app.api.admin_cognito import (
    _handle_delete_cognito_user,
    _handle_list_cognito_users,
    _handle_user_group,
)
from app.api.admin_crud import _handle_crud
from app.api.admin_feedback import (
    _handle_admin_feedback,
    _handle_user_feedback,
    _handle_user_feedback_labels,
)
from app.api.admin_imports import _handle_admin_imports
from app.api.admin_media import _handle_organization_media
from app.api.admin_request import (
    _decode_cursor,
    _encode_cursor,
    _parse_cursor,
    _parse_path,
    _query_param,
)
from app.api.admin_resources import (
    _RESOURCE_CONFIG,
    _validate_age_range,
    _validate_category_parent,
    _validate_coordinates,
    _validate_pricing_amount,
    _validate_schedule,
    _validate_sessions_count,
)
from app.api.admin_suggestions import _handle_user_organization_suggestion
from app.api.partner_auth import SCOPE_CRUD, get_partner_context
from app.api.admin_tickets import (
    _handle_admin_tickets,
    _handle_user_access_request,
)
from app.api.admin_validators import (
    MAX_DESCRIPTION_LENGTH,
    MAX_LANGUAGES_COUNT,
    MAX_MEDIA_URLS_COUNT,
    MAX_NAME_LENGTH,
    MAX_URL_LENGTH,
    _validate_currency,
    _validate_email,
    _validate_language_code,
    _validate_languages,
    _validate_logo_media_url,
    _validate_manager_id,
    _validate_media_urls,
    _validate_phone_fields,
    _validate_social_value,
    _validate_string_length,
    _validate_url,
)
from app.api.user_organizations import _handle_user_organizations
from app.exceptions import NotFoundError, ValidationError
from app.utils import json_response
from app.utils.logging import configure_logging, get_logger, set_request_context
from app.utils.responses import validate_content_type

configure_logging()
logger = get_logger(__name__)

__all__ = [
    "lambda_handler",
    "MAX_DESCRIPTION_LENGTH",
    "MAX_LANGUAGES_COUNT",
    "MAX_MEDIA_URLS_COUNT",
    "MAX_NAME_LENGTH",
    "MAX_URL_LENGTH",
    "_validate_age_range",
    "_validate_category_parent",
    "_validate_coordinates",
    "_validate_currency",
    "_validate_email",
    "_validate_language_code",
    "_validate_languages",
    "_validate_logo_media_url",
    "_validate_manager_id",
    "_validate_media_urls",
    "_validate_phone_fields",
    "_validate_pricing_amount",
    "_validate_schedule",
    "_validate_sessions_count",
    "_validate_social_value",
    "_validate_string_length",
    "_validate_url",
    "_decode_cursor",
    "_encode_cursor",
    "_parse_cursor",
]


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
        return _handle_user_routes(event, method, resource, resource_id)

    if base_path == "manager":
        return _handle_manager_routes(event, method, resource, resource_id)

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

    if resource == "users" and sub_resource == "groups":
        return _safe_handler(
            lambda: _handle_user_group(event, method, resource_id), event
        )
    if resource == "organizations" and sub_resource == "media":
        return _handle_organization_media(event, method, resource_id)
    if resource == "cognito-users" and method == "GET":
        return _safe_handler(lambda: _handle_list_cognito_users(event), event)
    if resource == "cognito-users" and method == "DELETE" and resource_id:
        return _safe_handler(
            lambda: _handle_delete_cognito_user(event, resource_id),
            event,
        )
    if resource == "tickets":
        return _safe_handler(
            lambda: _handle_admin_tickets(event, method, resource_id),
            event,
        )
    if resource == "organization-feedback":
        return _safe_handler(
            lambda: _handle_admin_feedback(event, method, resource_id),
            event,
        )
    if resource == "audit-logs" and method == "GET":
        return _safe_handler(lambda: _handle_audit_logs(event, resource_id), event)
    if resource == "api-keys":
        return _safe_handler(
            lambda: _handle_admin_api_keys(event, method, resource_id),
            event,
        )
    if resource == "imports":
        return _safe_handler(
            lambda: _handle_admin_imports(event, method, resource_id),
            event,
        )

    if (
        resource == "organizations"
        and method == "GET"
        and not resource_id
        and _is_importer(event)
        and not _is_admin(event)
        and not _query_param(event, "place_id")
        and not _query_param(event, "source_id")
    ):
        return json_response(403, {"error": "Forbidden"}, event=event)

    if resource == "areas":
        if method == "GET":
            return _safe_handler(
                lambda: _handle_list_areas(event, active_only=False),
                event,
            )
        if method == "PATCH" and resource_id:
            return _safe_handler(
                lambda: _handle_toggle_area(event, resource_id),
                event,
            )

    config = _RESOURCE_CONFIG.get(resource)
    if not config:
        return json_response(404, {"error": "Not found"}, event=event)

    return _safe_handler(
        lambda: _handle_crud(event, method, config, resource_id),
        event,
    )


def _importer_can_access(
    event: Mapping[str, Any],
    method: str,
    resource: str,
    resource_id: Optional[str],
) -> bool:
    """Allow importer JWTs on catalog import and owner-UI listing routes."""
    if not _is_importer(event):
        return False
    if resource == "imports":
        if method == "POST" and resource_id in (None, "presign"):
            return True
        if method == "GET" and resource_id and resource_id != "export":
            return True
        return False
    if resource == "organizations":
        if method == "GET":
            return True
        if method == "PATCH" and resource_id:
            return True
        return False
    return False


def _safe_handler(
    handler: Any,
    event: Mapping[str, Any],
) -> dict[str, Any]:
    """Execute a handler with common error handling."""
    try:
        return handler()
    except ValidationError as exc:
        logger.warning(f"Validation error: {exc.message}")
        return json_response(exc.status_code, exc.to_dict(), event=event)
    except NotFoundError as exc:
        return json_response(exc.status_code, exc.to_dict(), event=event)
    except ValueError as exc:
        logger.warning(f"Value error: {exc}")
        return json_response(400, {"error": str(exc)}, event=event)
    except Exception as exc:  # pragma: no cover
        logger.exception(f"Unexpected error in handler: {type(exc).__name__}")
        return json_response(500, {"error": "Internal server error"}, event=event)


def _handle_user_routes(
    event: Mapping[str, Any],
    method: str,
    resource: str,
    resource_id: Optional[str],
) -> dict[str, Any]:
    """Handle routes accessible to any logged-in Cognito user."""
    if resource == "access-request":
        return _safe_handler(
            lambda: _handle_user_access_request(event, method),
            event,
        )

    if resource == "address-search" and method == "GET":
        return _safe_handler(lambda: _handle_address_search(event), event)

    if resource == "organization-suggestion":
        return _safe_handler(
            lambda: _handle_user_organization_suggestion(event, method),
            event,
        )
    if resource == "organization-feedback":
        return _safe_handler(
            lambda: _handle_user_feedback(event, method),
            event,
        )
    if resource == "feedback-labels" and method == "GET":
        return _safe_handler(
            lambda: _handle_user_feedback_labels(event),
            event,
        )
    if resource == "organizations" and method == "GET":
        return _safe_handler(
            lambda: _handle_user_organizations(event, method),
            event,
        )

    if resource == "areas" and method == "GET":
        return _safe_handler(
            lambda: _handle_list_areas(event, active_only=True),
            event,
        )

    if resource == "activity-categories" and method == "GET":
        return _safe_handler(
            lambda: _handle_list_activity_categories(event),
            event,
        )

    return json_response(404, {"error": "Not found"}, event=event)


def _handle_manager_routes(
    event: Mapping[str, Any],
    method: str,
    resource: str,
    resource_id: Optional[str],
) -> dict[str, Any]:
    """Handle routes accessible to users in the 'manager' group."""
    if not _is_manager(event) and not _is_admin(event):
        logger.warning("Unauthorized manager access attempt")
        return json_response(403, {"error": "Forbidden"}, event=event)

    manager_resources = {
        "organizations",
        "locations",
        "activities",
        "pricing",
        "schedules",
    }
    if resource not in manager_resources:
        return json_response(404, {"error": "Not found"}, event=event)

    managed_org_ids = _get_managed_organization_ids(event)

    if not managed_org_ids:
        if method == "GET" and not resource_id:
            return json_response(200, {"items": [], "next_cursor": None}, event=event)
        return json_response(
            403, {"error": "You don't manage any organizations"}, event=event
        )

    config = _RESOURCE_CONFIG.get(resource)
    if not config:
        return json_response(404, {"error": "Not found"}, event=event)

    return _safe_handler(
        lambda: _handle_crud(event, method, config, resource_id, managed_org_ids),
        event,
    )


_PARTNER_RESOURCES = {
    "organizations",
    "locations",
    "activities",
    "pricing",
    "schedules",
}


def _handle_partner_routes(
    event: Mapping[str, Any],
    method: str,
    resource: str,
    resource_id: Optional[str],
) -> dict[str, Any]:
    """Handle CRUD routes authenticated with a partner API key.

    Keys with the ``read`` scope may only perform GET requests; ``crud``
    keys get full CRUD. Org-scoped keys are restricted to their
    organization's data (same filtering as manager routes); full-access
    keys behave like admin CRUD.
    """
    partner = get_partner_context(event)
    if partner is None:
        logger.warning("Partner route called without API-key context")
        return json_response(403, {"error": "Forbidden"}, event=event)

    if method != "GET" and partner.scope != SCOPE_CRUD:
        logger.warning("Partner key without crud scope attempted a write")
        return json_response(
            403,
            {"error": "This API key does not allow write access"},
            event=event,
        )

    if resource not in _PARTNER_RESOURCES:
        return json_response(404, {"error": "Not found"}, event=event)

    managed_org_ids = {partner.org_id} if partner.org_id else None

    # An org-scoped key cannot create organizations: any new organization
    # would fall outside the key's scope.
    if managed_org_ids is not None and resource == "organizations":
        if method == "POST":
            return json_response(
                403,
                {"error": "Organization-scoped keys cannot create organizations"},
                event=event,
            )

    config = _RESOURCE_CONFIG.get(resource)
    if not config:
        return json_response(404, {"error": "Not found"}, event=event)

    return _safe_handler(
        lambda: _handle_crud(event, method, config, resource_id, managed_org_ids),
        event,
    )
