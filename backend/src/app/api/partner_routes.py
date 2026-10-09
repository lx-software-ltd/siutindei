"""Partner API-key route dispatch."""

from __future__ import annotations

from typing import Any, Mapping, Optional

from app.api.admin_crud import _handle_crud
from app.api.admin_resources import _RESOURCE_CONFIG
from app.api.partner_activity_categories import (
    handle_partner_activity_categories,
)
from app.api.partner_auth import SCOPE_CRUD, get_partner_context
from app.api.partner_category_reviews import (
    handle_partner_category_review_write,
    handle_partner_category_reviews,
    partner_get_activities,
)
from app.api.partner_name_fixes import (
    handle_partner_name_fixes,
    partner_get_organizations,
)
from app.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.utils import json_response
from app.utils.logging import get_logger

logger = get_logger(__name__)

_PARTNER_RESOURCES = {
    "organizations",
    "locations",
    "activities",
    "pricing",
    "schedules",
}


def handle_partner_routes(
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

    if resource == "name-fixes":
        if method != "GET":
            return json_response(404, {"error": "Not found"}, event=event)
        return _safe_handler(
            lambda: handle_partner_name_fixes(event, partner.org_id),
            event,
        )

    if resource == "category-reviews":
        if method == "GET" and resource_id is None:
            return _safe_handler(
                lambda: handle_partner_category_reviews(event, partner.org_id),
                event,
            )
        if method == "POST" and resource_id:
            return _safe_handler(
                lambda: handle_partner_category_review_write(
                    event, partner, resource_id
                ),
                event,
            )
        return json_response(404, {"error": "Not found"}, event=event)

    if resource == "activity-categories":
        return _safe_handler(
            lambda: handle_partner_activity_categories(
                event, method, partner, resource_id
            ),
            event,
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

    if resource == "organizations" and method == "GET":
        return _safe_handler(
            lambda: partner_get_organizations(event, resource_id, managed_org_ids),
            event,
        )

    if resource == "activities" and method == "GET":
        return _safe_handler(
            lambda: partner_get_activities(event, resource_id, managed_org_ids),
            event,
        )

    config = _RESOURCE_CONFIG.get(resource)
    if not config:
        return json_response(404, {"error": "Not found"}, event=event)

    return _safe_handler(
        lambda: _handle_crud(event, method, config, resource_id, managed_org_ids),
        event,
    )


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
    except AuthorizationError as exc:
        logger.warning(f"Authorization error: {exc.message}")
        return json_response(exc.status_code, exc.to_dict(), event=event)
    except NotFoundError as exc:
        return json_response(exc.status_code, exc.to_dict(), event=event)
    except ValueError as exc:
        logger.warning(f"Value error: {exc}")
        return json_response(400, {"error": str(exc)}, event=event)
    except Exception as exc:  # pragma: no cover
        logger.exception(f"Unexpected error in handler: {type(exc).__name__}")
        return json_response(500, {"error": "Internal server error"}, event=event)
