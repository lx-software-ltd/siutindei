"""Route table for admin, user, and manager resources.

The first matching admin row wins. Those rows run before generic CRUD.
Importer organization-list denial still runs after the special rows.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from app.api.admin_auth import (
    _get_managed_organization_ids,
    _is_admin,
    _is_importer,
    _is_manager,
)
from app.api.admin_request import _query_param
from app.exceptions import AppError, NotFoundError, ValidationError
from app.utils import json_response
from app.utils.logging import get_logger

logger = get_logger(__name__)

_ANY = object()
Handler = Callable[
    [Mapping[str, Any], str, str | None, str | None],
    dict[str, Any],
]


class AdminRoute:
    """One admin resource row."""

    def __init__(
        self,
        resource: str,
        handler: Handler,
        *,
        methods: frozenset[str] | None = None,
        sub: Any = _ANY,
        has_id: bool | None = None,
        admin_only: bool = False,
        safe: bool = True,
    ) -> None:
        self.resource = resource
        self.handler = handler
        self.methods = methods
        self.sub = sub
        self.has_id = has_id
        self.admin_only = admin_only
        self.safe = safe

    def matches(
        self,
        method: str,
        resource: str,
        resource_id: str | None,
        sub_resource: str | None,
    ) -> bool:
        if resource != self.resource:
            return False
        if self.sub is not _ANY and sub_resource != self.sub:
            return False
        if self.methods is not None and method not in self.methods:
            return False
        if self.has_id is True and not resource_id:
            return False
        return not (self.has_id is False and resource_id)


def _safe_handler(handler: Any, event: Mapping[str, Any]) -> dict[str, Any]:
    """Execute a handler with common error handling."""
    try:
        return handler()
    except ValidationError as exc:
        logger.warning(f"Validation error: {exc.message}")
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


def _call(
    handler: Handler,
    event: Mapping[str, Any],
    method: str,
    resource_id: str | None,
    sub: str | None,
    *,
    safe: bool,
) -> dict[str, Any]:
    if not safe:
        return handler(event, method, resource_id, sub)
    return _safe_handler(lambda: handler(event, method, resource_id, sub), event)


def _user_group(
    event: Mapping[str, Any], method: str, resource_id: str | None, _sub: str | None
) -> dict[str, Any]:
    from app.api.admin_cognito import _handle_user_group

    return _handle_user_group(event, method, resource_id)


def _org_media(
    event: Mapping[str, Any], method: str, resource_id: str | None, _sub: str | None
) -> dict[str, Any]:
    from app.api.admin_media import _handle_organization_media

    return _handle_organization_media(event, method, resource_id)


def _org_enrichment(
    event: Mapping[str, Any], method: str, resource_id: str | None, _sub: str | None
) -> dict[str, Any]:
    from app.api import admin as admin_api

    return admin_api.handle_org_enrichment(event, method, resource_id)


def _cognito_collection(
    event: Mapping[str, Any], method: str, _resource_id: str | None, _sub: str | None
) -> dict[str, Any]:
    from app.api.admin_cognito import _handle_list_cognito_users
    from app.api.admin_cognito_manager import _handle_create_cognito_manager

    if method == "GET":
        return _handle_list_cognito_users(event)
    if method == "POST":
        return _handle_create_cognito_manager(event)
    return json_response(405, {"error": "Method not allowed"}, event=event)


def _cognito_delete(
    event: Mapping[str, Any], _method: str, resource_id: str | None, _sub: str | None
) -> dict[str, Any]:
    from app.api.admin_cognito import _handle_delete_cognito_user

    if resource_id is None:
        return json_response(404, {"error": "Not found"}, event=event)
    return _handle_delete_cognito_user(event, resource_id)


def _tickets(
    event: Mapping[str, Any], method: str, resource_id: str | None, _sub: str | None
) -> dict[str, Any]:
    from app.api.admin_tickets import _handle_admin_tickets

    return _handle_admin_tickets(event, method, resource_id)


def _feedback(
    event: Mapping[str, Any], method: str, resource_id: str | None, _sub: str | None
) -> dict[str, Any]:
    from app.api.admin_feedback import _handle_admin_feedback

    return _handle_admin_feedback(event, method, resource_id)


def _audit(
    event: Mapping[str, Any], _method: str, resource_id: str | None, _sub: str | None
) -> dict[str, Any]:
    from app.api.admin_audit import _handle_audit_logs

    return _handle_audit_logs(event, resource_id)


def _api_keys(
    event: Mapping[str, Any], method: str, resource_id: str | None, _sub: str | None
) -> dict[str, Any]:
    from app.api.admin_api_keys import _handle_admin_api_keys

    return _handle_admin_api_keys(event, method, resource_id)


def _enrichment_settings(
    event: Mapping[str, Any], method: str, _resource_id: str | None, _sub: str | None
) -> dict[str, Any]:
    from app.api.admin_enrichment import handle_enrichment_settings

    return handle_enrichment_settings(event, method)


def _import_settings(
    event: Mapping[str, Any], method: str, _resource_id: str | None, _sub: str | None
) -> dict[str, Any]:
    from app.api.admin_import_settings import handle_import_settings

    return handle_import_settings(event, method)


def _data_quality(
    event: Mapping[str, Any], method: str, resource_id: str | None, sub: str | None
) -> dict[str, Any]:
    from app.api.admin_data_quality import handle_data_quality

    return handle_data_quality(event, method, resource_id, sub)


def _imports(
    event: Mapping[str, Any], method: str, resource_id: str | None, _sub: str | None
) -> dict[str, Any]:
    from app.api import admin as admin_api

    return admin_api._handle_admin_imports(event, method, resource_id)


def _category_suggestions(
    event: Mapping[str, Any], method: str, resource_id: str | None, sub: str | None
) -> dict[str, Any]:
    from app.api.admin_category_suggestions import _handle_admin_category_suggestions

    return _handle_admin_category_suggestions(event, method, resource_id, sub)


def _org_review(
    event: Mapping[str, Any], method: str, resource_id: str | None, sub: str | None
) -> dict[str, Any]:
    from app.api.admin_org_review import _handle_admin_org_review

    return _handle_admin_org_review(event, method, resource_id, sub)


def _versions(
    event: Mapping[str, Any], method: str, resource_id: str | None, sub: str | None
) -> dict[str, Any]:
    from app.api.admin_versions import handle_versions

    return handle_versions(event, method, resource_id, sub)


def _deleted_organizations(
    event: Mapping[str, Any], method: str, resource_id: str | None, _sub: str | None
) -> dict[str, Any]:
    from app.api.admin_deleted_organizations import handle_deleted_organizations

    return handle_deleted_organizations(event, method, resource_id)


def _org_duplicates(
    event: Mapping[str, Any], method: str, resource_id: str | None, sub: str | None
) -> dict[str, Any]:
    from app.api.admin_org_duplicates import handle_org_duplicates

    return handle_org_duplicates(event, method, resource_id, sub)


def _name_fixes(
    event: Mapping[str, Any], method: str, resource_id: str | None, sub: str | None
) -> dict[str, Any]:
    from app.api.admin_name_fixes import handle_name_fixes

    return handle_name_fixes(event, method, resource_id, sub)


def _location_fixes(
    event: Mapping[str, Any], method: str, resource_id: str | None, sub: str | None
) -> dict[str, Any]:
    from app.api.admin_location_fixes import handle_location_fixes

    return handle_location_fixes(event, method, resource_id, sub)


def _translation_fixes(
    event: Mapping[str, Any], method: str, resource_id: str | None, sub: str | None
) -> dict[str, Any]:
    from app.api.admin_translation_fixes import handle_translation_fixes

    return handle_translation_fixes(event, method, resource_id, sub)


def _areas_list(
    event: Mapping[str, Any], _method: str, _resource_id: str | None, _sub: str | None
) -> dict[str, Any]:
    from app.api.admin_areas import _handle_list_areas

    return _handle_list_areas(event, active_only=False)


def _areas_toggle(
    event: Mapping[str, Any], _method: str, resource_id: str | None, _sub: str | None
) -> dict[str, Any]:
    from app.api.admin_areas import _handle_toggle_area

    if resource_id is None:
        return json_response(404, {"error": "Not found"}, event=event)
    return _handle_toggle_area(event, resource_id)


_ADMIN_ROUTES: tuple[AdminRoute, ...] = (
    AdminRoute("users", _user_group, sub="groups"),
    AdminRoute("organizations", _org_media, sub="media", safe=False),
    AdminRoute("organizations", _org_enrichment, sub="enrichment"),
    AdminRoute("cognito-users", _cognito_collection, has_id=False),
    AdminRoute(
        "cognito-users", _cognito_delete, methods=frozenset({"DELETE"}), has_id=True
    ),
    AdminRoute("tickets", _tickets),
    AdminRoute("organization-feedback", _feedback),
    AdminRoute("audit-logs", _audit, methods=frozenset({"GET"})),
    AdminRoute("api-keys", _api_keys),
    AdminRoute("enrichment-settings", _enrichment_settings, admin_only=True),
    AdminRoute("import-settings", _import_settings, admin_only=True),
    AdminRoute("data-quality", _data_quality, admin_only=True),
    AdminRoute("imports", _imports),
    AdminRoute("category-suggestions", _category_suggestions, admin_only=True),
    AdminRoute("org-review", _org_review),
    AdminRoute("versions", _versions, admin_only=True),
    AdminRoute("deleted-organizations", _deleted_organizations, admin_only=True),
    AdminRoute("org-duplicates", _org_duplicates, admin_only=True),
    AdminRoute("name-fixes", _name_fixes, admin_only=True),
    AdminRoute("location-fixes", _location_fixes, admin_only=True),
    AdminRoute("translation-fixes", _translation_fixes, admin_only=True),
    AdminRoute("areas", _areas_list, methods=frozenset({"GET"})),
    AdminRoute("areas", _areas_toggle, methods=frozenset({"PATCH"}), has_id=True),
)


def dispatch_admin(
    event: Mapping[str, Any],
    method: str,
    resource: str,
    resource_id: str | None,
    sub_resource: str | None,
) -> dict[str, Any]:
    """Match one admin route, then the importer list guard, then CRUD."""
    for route in _ADMIN_ROUTES:
        if not route.matches(method, resource, resource_id, sub_resource):
            continue
        if route.admin_only and not _is_admin(event):
            return json_response(403, {"error": "Forbidden"}, event=event)
        return _call(
            route.handler,
            event,
            method,
            resource_id,
            sub_resource,
            safe=route.safe,
        )
    denied = _importer_organization_list_forbidden(event, method, resource, resource_id)
    if denied is not None:
        return denied
    if sub_resource:
        return json_response(404, {"error": "Not found"}, event=event)
    return _crud(event, method, resource, resource_id)


def _importer_organization_list_forbidden(
    event: Mapping[str, Any],
    method: str,
    resource: str,
    resource_id: str | None,
) -> dict[str, Any] | None:
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
    return None


def _crud(
    event: Mapping[str, Any],
    method: str,
    resource: str,
    resource_id: str | None,
) -> dict[str, Any]:
    from app.api import admin as admin_api
    from app.api.admin_resources import _RESOURCE_CONFIG

    config = _RESOURCE_CONFIG.get(resource)
    if not config:
        return json_response(404, {"error": "Not found"}, event=event)
    return _safe_handler(
        lambda: admin_api._handle_crud(event, method, config, resource_id),
        event,
    )


def handle_user_routes(
    event: Mapping[str, Any],
    method: str,
    resource: str,
    resource_id: str | None,
) -> dict[str, Any]:
    """Handle routes accessible to any logged-in Cognito user."""
    if resource == "access-request":
        from app.api.admin_tickets import _handle_user_access_request

        return _safe_handler(lambda: _handle_user_access_request(event, method), event)
    if resource == "address-search" and method == "GET":
        from app.api.admin_address_search import _handle_address_search

        return _safe_handler(lambda: _handle_address_search(event), event)
    if resource == "organization-suggestion":
        from app.api.admin_suggestions import _handle_user_organization_suggestion

        return _safe_handler(
            lambda: _handle_user_organization_suggestion(event, method),
            event,
        )
    if resource == "organization-feedback":
        from app.api.admin_feedback import _handle_user_feedback

        return _safe_handler(lambda: _handle_user_feedback(event, method), event)
    if resource == "feedback-labels" and method == "GET":
        from app.api.admin_feedback import _handle_user_feedback_labels

        return _safe_handler(lambda: _handle_user_feedback_labels(event), event)
    if resource == "organizations" and method == "GET":
        from app.api.user_organizations import _handle_user_organizations

        return _safe_handler(lambda: _handle_user_organizations(event, method), event)
    if resource == "areas" and method == "GET":
        from app.api.admin_areas import _handle_list_areas

        return _safe_handler(lambda: _handle_list_areas(event, active_only=True), event)
    if resource == "activity-categories" and method == "GET":
        from app.api.admin_areas import _handle_list_activity_categories

        return _safe_handler(lambda: _handle_list_activity_categories(event), event)
    return json_response(404, {"error": "Not found"}, event=event)


def handle_manager_routes(
    event: Mapping[str, Any],
    method: str,
    resource: str,
    resource_id: str | None,
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
            403,
            {"error": "You don't manage any organizations"},
            event=event,
        )

    from app.api import admin as admin_api
    from app.api.admin_resources import _RESOURCE_CONFIG

    config = _RESOURCE_CONFIG.get(resource)
    if not config:
        return json_response(404, {"error": "Not found"}, event=event)
    return _safe_handler(
        lambda: admin_api._handle_crud(
            event,
            method,
            config,
            resource_id,
            managed_org_ids,
        ),
        event,
    )
