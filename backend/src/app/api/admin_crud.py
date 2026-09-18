"""Shared CRUD handlers for admin and manager routes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional, Protocol, Sequence, Type
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.admin_auth import _set_session_audit_context
from app.api.admin_request import (
    _encode_cursor,
    _parse_body,
    _parse_cursor,
    _parse_uuid,
    _query_param,
    parse_limit,
)
from app.db.engine import get_engine
from app.db.models import Activity, Organization
from app.db.repositories import ActivityRepository
from app.exceptions import NotFoundError, ValidationError
from app.utils import json_response
from app.utils.logging import get_logger

logger = get_logger(__name__)


class RepositoryProtocol(Protocol):
    """Protocol for repository classes used in ResourceConfig."""

    def __init__(self, session: Session) -> None: ...

    def get_by_id(self, entity_id: UUID) -> Any: ...

    def get_all(
        self, limit: int = 50, cursor: Optional[UUID] = None
    ) -> Sequence[Any]: ...

    def create(self, entity: Any) -> Any: ...

    def update(self, entity: Any) -> Any: ...

    def delete(self, entity: Any) -> None: ...


@dataclass(frozen=True)
class ResourceConfig:
    """Configuration for admin resources."""

    name: str
    model: Type[Any]
    repository_class: Type[RepositoryProtocol]
    serializer: Callable[[Any], dict[str, Any]]
    create_handler: Callable[..., Any]
    update_handler: Callable[..., Any]
    # Optional: different update handler for manager routes (e.g., to restrict fields)
    manager_update_handler: Optional[Callable[..., Any]] = None


def _handle_crud(
    event: Mapping[str, Any],
    method: str,
    config: ResourceConfig,
    resource_id: Optional[str],
    managed_org_ids: Optional[set[str]] = None,
) -> dict[str, Any]:
    """Unified CRUD handler for both admin and manager routes.

    Args:
        event: The Lambda event.
        method: HTTP method (GET, POST, PUT, DELETE).
        config: Resource configuration.
        resource_id: Optional specific resource ID.
        managed_org_ids: If set, filter/validate by organization management.

    Returns:
        API Gateway response.
    """
    if method == "POST" and resource_id:
        return json_response(
            405,
            {"error": "Method not allowed"},
            event=event,
        )

    with Session(get_engine()) as session:
        # Set audit context for trigger-based audit logging
        _set_session_audit_context(session, event)

        if method == "GET":
            return _crud_get(event, session, config, resource_id, managed_org_ids)
        if method == "POST":
            return _crud_post(event, session, config, managed_org_ids)
        if method in ("PUT", "PATCH"):
            return _crud_put(event, session, config, resource_id, managed_org_ids)
        if method == "DELETE":
            return _crud_delete(event, session, config, resource_id, managed_org_ids)

    return json_response(405, {"error": "Method not allowed"}, event=event)


def _crud_get(
    event: Mapping[str, Any],
    session: Session,
    config: ResourceConfig,
    resource_id: Optional[str],
    managed_org_ids: Optional[set[str]] = None,
) -> dict[str, Any]:
    """Handle GET requests with optional management filtering."""
    limit = parse_limit(event)

    repo = config.repository_class(session)

    if resource_id:
        entity = repo.get_by_id(_parse_uuid(resource_id))
        if entity is None:
            raise NotFoundError(config.name, resource_id)
        # Check management if filtering is enabled
        if managed_org_ids is not None:
            entity_org_id = _get_entity_org_id(entity, session)
            if entity_org_id not in managed_org_ids:
                return json_response(
                    403,
                    {"error": "You don't have access to this resource"},
                    event=event,
                )
        return json_response(200, config.serializer(entity), event=event)

    # List resources
    if config.name == "organizations":
        lookup = _lookup_organization(session, event, managed_org_ids)
        if lookup is not None:
            return lookup
    cursor = _parse_cursor(_query_param(event, "cursor"))
    if managed_org_ids is not None:
        rows = _get_all_filtered_by_org(
            session, config, managed_org_ids, limit + 1, cursor
        )
    else:
        rows = repo.get_all(limit=limit + 1, cursor=cursor)

    has_more = len(rows) > limit
    trimmed = list(rows)[:limit]
    next_cursor = _encode_cursor(trimmed[-1].id) if has_more and trimmed else None

    return json_response(
        200,
        {
            "items": [config.serializer(row) for row in trimmed],
            "next_cursor": next_cursor,
        },
        event=event,
    )


def _crud_post(
    event: Mapping[str, Any],
    session: Session,
    config: ResourceConfig,
    managed_org_ids: Optional[set[str]] = None,
) -> dict[str, Any]:
    """Handle POST requests with optional management validation."""
    body = _parse_body(event)

    # Validate management if filtering is enabled
    if managed_org_ids is not None:
        org_id = _get_org_id_from_body(body, config.name)
        if org_id and org_id not in managed_org_ids:
            return json_response(
                403,
                {"error": "You don't have access to this organization"},
                event=event,
            )
        # For pricing/schedules, verify management through activity
        if config.name in ("pricing", "schedules"):
            activity_id = body.get("activity_id")
            if activity_id:
                activity_repo = ActivityRepository(session)
                activity = activity_repo.get_by_id(_parse_uuid(activity_id))
                if activity and str(activity.org_id) not in managed_org_ids:
                    return json_response(
                        403,
                        {"error": "You don't have access to this activity"},
                        event=event,
                    )

    repo = config.repository_class(session)
    entity = config.create_handler(repo, body)
    repo.create(entity)
    session.commit()
    session.refresh(entity)
    logger.info(f"Created {config.name}: {entity.id}")
    return json_response(201, config.serializer(entity), event=event)


def _crud_put(
    event: Mapping[str, Any],
    session: Session,
    config: ResourceConfig,
    resource_id: Optional[str],
    managed_org_ids: Optional[set[str]] = None,
) -> dict[str, Any]:
    """Handle PUT requests with optional management validation."""
    if not resource_id:
        raise ValidationError("Resource id is required", field="id")

    repo = config.repository_class(session)
    entity = repo.get_by_id(_parse_uuid(resource_id))
    if entity is None:
        raise NotFoundError(config.name, resource_id)

    # Check management if filtering is enabled
    if managed_org_ids is not None:
        entity_org_id = _get_entity_org_id(entity, session)
        if entity_org_id not in managed_org_ids:
            return json_response(
                403,
                {"error": "You don't have access to this resource"},
                event=event,
            )

    body = _parse_body(event)

    # Use manager-specific update handler if available and in manager mode
    if managed_org_ids is not None and config.manager_update_handler is not None:
        update_handler = config.manager_update_handler
    else:
        update_handler = config.update_handler

    updated = update_handler(repo, entity, body)
    repo.update(updated)
    session.commit()
    session.refresh(updated)
    logger.info(f"Updated {config.name}: {resource_id}")
    return json_response(200, config.serializer(updated), event=event)


def _crud_delete(
    event: Mapping[str, Any],
    session: Session,
    config: ResourceConfig,
    resource_id: Optional[str],
    managed_org_ids: Optional[set[str]] = None,
) -> dict[str, Any]:
    """Handle DELETE requests with optional management validation."""
    if not resource_id:
        raise ValidationError("Resource id is required", field="id")

    repo = config.repository_class(session)
    entity = repo.get_by_id(_parse_uuid(resource_id))
    if entity is None:
        raise NotFoundError(config.name, resource_id)

    # Check management if filtering is enabled
    if managed_org_ids is not None:
        entity_org_id = _get_entity_org_id(entity, session)
        if entity_org_id not in managed_org_ids:
            return json_response(
                403,
                {"error": "You don't have access to this resource"},
                event=event,
            )

    repo.delete(entity)
    session.commit()
    logger.info(f"Deleted {config.name}: {resource_id}")
    return json_response(204, {}, event=event)


def _get_entity_org_id(entity: Any, session: Session) -> Optional[str]:
    """Get the organization ID for an entity.

    Works for:
    - Organization: the entity's own ID
    - Location, Activity: direct org_id field
    - Pricing, Schedule: through activity relationship

    Returns:
        The organization ID as a string, or None if not determinable.
    """
    # Organization entity - the org_id is the entity itself
    if isinstance(entity, Organization):
        return str(entity.id)

    # Direct org_id (Location, Activity)
    if hasattr(entity, "org_id"):
        return str(entity.org_id)

    # Through activity (Pricing, Schedule)
    if hasattr(entity, "activity_id"):
        activity_repo = ActivityRepository(session)
        activity = activity_repo.get_by_id(entity.activity_id)
        if activity:
            return str(activity.org_id)

    return None


def _lookup_organization(
    session: Session,
    event: Mapping[str, Any],
    managed_org_ids: Optional[set[str]] = None,
) -> dict[str, Any] | None:
    """Resolve GET /organizations?place_id= or ?source_id= lookups."""
    from app.api.admin_imports_catalog import (
        find_org_by_place_id,
        find_org_by_source_id,
    )
    from app.api.admin_resource_organization import _serialize_organization

    place_id = _query_param(event, "place_id")
    source_id = _query_param(event, "source_id")
    if not place_id and not source_id:
        return None
    entity = None
    if place_id:
        entity = find_org_by_place_id(session, place_id.strip())
    if entity is None and source_id:
        entity = find_org_by_source_id(session, source_id.strip())
    if (
        entity is not None
        and managed_org_ids is not None
        and str(entity.id) not in managed_org_ids
    ):
        entity = None
    items = [_serialize_organization(entity)] if entity is not None else []
    return json_response(
        200,
        {"items": items, "next_cursor": None},
        event=event,
    )


def _get_org_id_from_body(body: dict[str, Any], resource_name: str) -> Optional[str]:
    """Extract the organization ID from a request body.

    For locations/activities, reads org_id directly.
    For pricing/schedules, would need to look up via activity_id (handled separately).

    Returns:
        The organization ID as a string, or None if not in body.
    """
    org_id = body.get("org_id")
    if org_id:
        return str(org_id)
    return None


def _get_all_filtered_by_org(
    session: Session,
    config: ResourceConfig,
    managed_org_ids: set[str],
    limit: int,
    cursor: Optional[UUID],
) -> Sequence[Any]:
    """Get all entities filtered by organization management.

    Args:
        session: Database session.
        config: Resource configuration.
        managed_org_ids: Set of managed organization IDs.
        limit: Maximum results to return.
        cursor: Optional pagination cursor.

    Returns:
        Sequence of entities belonging to the managed organizations.
    """
    model = config.model

    # Build base query based on model type
    if model == Organization:
        # Organization - filter by entity ID
        query = select(model).where(model.id.in_(managed_org_ids))
    elif hasattr(model, "org_id"):
        # Direct org_id (Location, Activity)
        query = select(model).where(model.org_id.in_(managed_org_ids))
    elif hasattr(model, "activity_id"):
        # Through activity (Pricing, Schedule)
        query = (
            select(model)
            .join(Activity, model.activity_id == Activity.id)
            .where(Activity.org_id.in_(managed_org_ids))
        )
    else:
        # Default to empty query
        return []

    if cursor is not None:
        query = query.where(model.id > cursor)
    return session.execute(query.order_by(model.id).limit(limit)).scalars().all()
