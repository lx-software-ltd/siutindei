"""Partner API-key route dispatch."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from app.api.admin_crud import _handle_crud
from app.api.admin_enrichment import organization_tail
from app.api.admin_resources import _RESOURCE_CONFIG
from app.api.partner_activity_categories import (
    handle_partner_activity_categories,
)
from app.api.partner_auth import (
    SCOPE_CRUD,
    PartnerContext,
    get_partner_context,
    require_crud,
    require_full_access,
)
from app.api.partner_category_reviews import (
    handle_partner_category_review_write,
    handle_partner_category_reviews,
    partner_get_activities,
)
from app.api.partner_location_fixes import (
    handle_partner_location_fix_write,
    handle_partner_location_fixes,
)
from app.api.partner_name_fixes import (
    handle_partner_name_fixes,
    partner_get_organizations,
)
from app.api.partner_org_enrichment import (
    handle_partner_enrichment_settings,
    handle_partner_org_enrichment,
)
from app.api.partner_org_merge import handle_partner_org_merge
from app.api.partner_org_reject import handle_partner_org_reject
from app.exceptions import AppError, AuthorizationError, NotFoundError, ValidationError
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

PartnerHandler = Callable[
    [Mapping[str, Any], str, str | None, PartnerContext],
    dict[str, Any],
]


class PartnerRoute:
    """One partner resource row.

    ``full_access`` is the admin equivalent: a full-access ``crud`` key.
    An organization-scoped key is rejected before the handler runs, and
    the handler checks again.
    """

    def __init__(
        self,
        resource: str,
        handler: PartnerHandler,
        *,
        methods: frozenset[str] | None = None,
        has_id: bool | None = None,
        full_access: bool = False,
        crud_only: bool = False,
        tail: str | None = None,
        overlay: bool = False,
    ) -> None:
        self.resource = resource
        self.handler = handler
        self.methods = methods
        self.has_id = has_id
        self.full_access = full_access
        self.crud_only = crud_only
        self.tail = tail
        self.overlay = overlay

    def matches(
        self,
        method: str,
        resource_id: str | None,
        event: Mapping[str, Any],
    ) -> bool:
        if self.methods is not None and method not in self.methods:
            return False
        if self.has_id is True and not resource_id:
            return False
        if self.has_id is False and resource_id:
            return False
        if self.tail is None:
            return True
        segments = organization_tail(str(event.get("path") or ""))
        return bool(segments) and segments[0] == self.tail


def _partner_name_fixes(
    event: Mapping[str, Any],
    _method: str,
    _resource_id: str | None,
    partner: PartnerContext,
) -> dict[str, Any]:
    return handle_partner_name_fixes(event, partner.org_id)


def _partner_location_fixes(
    event: Mapping[str, Any],
    _method: str,
    _resource_id: str | None,
    partner: PartnerContext,
) -> dict[str, Any]:
    return handle_partner_location_fixes(event, partner.org_id)


def _partner_location_fix_write(
    event: Mapping[str, Any],
    _method: str,
    resource_id: str | None,
    partner: PartnerContext,
) -> dict[str, Any]:
    return handle_partner_location_fix_write(event, partner, resource_id or "")


def _partner_category_reviews(
    event: Mapping[str, Any],
    _method: str,
    _resource_id: str | None,
    partner: PartnerContext,
) -> dict[str, Any]:
    return handle_partner_category_reviews(event, partner.org_id)


def _partner_category_review_write(
    event: Mapping[str, Any],
    _method: str,
    resource_id: str | None,
    partner: PartnerContext,
) -> dict[str, Any]:
    return handle_partner_category_review_write(event, partner, resource_id or "")


def _partner_activity_categories(
    event: Mapping[str, Any],
    method: str,
    resource_id: str | None,
    partner: PartnerContext,
) -> dict[str, Any]:
    return handle_partner_activity_categories(event, method, partner, resource_id)


def _partner_org_enrichment(
    event: Mapping[str, Any],
    method: str,
    resource_id: str | None,
    partner: PartnerContext,
) -> dict[str, Any]:
    return handle_partner_org_enrichment(event, method, resource_id, partner)


def _partner_enrichment_settings(
    event: Mapping[str, Any],
    method: str,
    _resource_id: str | None,
    partner: PartnerContext,
) -> dict[str, Any]:
    return handle_partner_enrichment_settings(event, method, partner)


def _partner_org_merge(
    event: Mapping[str, Any],
    _method: str,
    _resource_id: str | None,
    partner: PartnerContext,
) -> dict[str, Any]:
    return handle_partner_org_merge(event, partner)


def _partner_org_reject(
    event: Mapping[str, Any],
    method: str,
    resource_id: str | None,
    partner: PartnerContext,
) -> dict[str, Any]:
    return handle_partner_org_reject(event, method, resource_id, partner)


_PARTNER_ROUTES = (
    PartnerRoute(
        "name-fixes",
        _partner_name_fixes,
        methods=frozenset({"GET"}),
        has_id=False,
    ),
    PartnerRoute(
        "location-fixes",
        _partner_location_fixes,
        methods=frozenset({"GET"}),
        has_id=False,
    ),
    PartnerRoute(
        "location-fixes",
        _partner_location_fix_write,
        methods=frozenset({"POST"}),
        has_id=True,
        full_access=True,
    ),
    PartnerRoute(
        "category-reviews",
        _partner_category_reviews,
        methods=frozenset({"GET"}),
        has_id=False,
    ),
    PartnerRoute(
        "category-reviews",
        _partner_category_review_write,
        methods=frozenset({"POST"}),
        has_id=True,
        full_access=True,
    ),
    PartnerRoute(
        "activity-categories",
        _partner_activity_categories,
        full_access=True,
    ),
    PartnerRoute(
        "organization-merges",
        _partner_org_merge,
        methods=frozenset({"POST"}),
        has_id=False,
        full_access=True,
    ),
    PartnerRoute(
        "organizations",
        _partner_org_reject,
        methods=frozenset({"POST"}),
        has_id=True,
        full_access=True,
        crud_only=True,
        tail="reject",
        overlay=True,
    ),
    PartnerRoute(
        "organizations",
        _partner_org_enrichment,
        methods=frozenset({"GET", "POST"}),
        has_id=True,
        full_access=True,
        crud_only=True,
        tail="enrichment",
        overlay=True,
    ),
    PartnerRoute(
        "enrichment-settings",
        _partner_enrichment_settings,
        methods=frozenset({"GET", "PUT"}),
        has_id=False,
        full_access=True,
        crud_only=True,
    ),
)


def handle_partner_routes(
    event: Mapping[str, Any],
    method: str,
    resource: str,
    resource_id: str | None,
) -> dict[str, Any]:
    """Handle routes authenticated with a partner API key.

    ``read`` keys may only GET. ``crud`` keys may write. A full-access
    ``crud`` key, one with no organization, is the partner equivalent of
    an admin. Org-scoped keys stay inside their organization.
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

    listed = _dispatch_listed(event, method, resource, resource_id, partner)
    if listed is not None:
        return listed

    if resource not in _PARTNER_RESOURCES:
        return json_response(404, {"error": "Not found"}, event=event)

    managed_org_ids = {partner.org_id} if partner.org_id else None

    # An org-scoped key cannot create organizations: any new organization
    # would fall outside the key's scope.
    if managed_org_ids is not None and resource == "organizations" and method == "POST":
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


def _dispatch_listed(
    event: Mapping[str, Any],
    method: str,
    resource: str,
    resource_id: str | None,
    partner: PartnerContext,
) -> dict[str, Any] | None:
    """Dispatch a row from ``_PARTNER_ROUTES``. Unknown rows return None."""
    routes = [route for route in _PARTNER_ROUTES if route.resource == resource]
    if not routes:
        return None
    for route in routes:
        if not route.matches(method, resource_id, event):
            continue
        return _safe_handler(
            lambda route=route: _run_partner_route(
                route, event, method, resource_id, partner
            ),
            event,
        )
    segments = organization_tail(str(event.get("path") or ""))
    overlay_tails = {route.tail for route in routes if route.overlay and route.tail}
    if segments and segments[0] in overlay_tails:
        return json_response(404, {"error": "Not found"}, event=event)
    if any(not route.overlay for route in routes):
        return json_response(404, {"error": "Not found"}, event=event)
    return None


def _run_partner_route(
    route: PartnerRoute,
    event: Mapping[str, Any],
    method: str,
    resource_id: str | None,
    partner: PartnerContext,
) -> dict[str, Any]:
    if route.full_access:
        require_full_access(partner)
    if route.crud_only:
        require_crud(partner)
    return route.handler(event, method, resource_id, partner)


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
    except AppError as exc:
        logger.warning(f"Application error: {exc.message}")
        return json_response(exc.status_code, exc.to_dict(), event=event)
    except ValueError as exc:
        logger.warning(f"Value error: {exc}")
        return json_response(400, {"error": str(exc)}, event=event)
    except Exception as exc:  # pragma: no cover
        logger.exception(f"Unexpected error in handler: {type(exc).__name__}")
        return json_response(500, {"error": "Internal server error"}, event=event)
