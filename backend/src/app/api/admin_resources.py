"""Resource configuration for admin CRUD."""

from __future__ import annotations

from app.api.admin_crud import ResourceConfig
from app.api.admin_resource_activity import (
    _create_activity,
    _serialize_activity,
    _update_activity,
    _update_activity_for_manager,
    _validate_age_range,
)
from app.api.admin_resource_activity_category import (
    _create_activity_category,
    _serialize_activity_category,
    _update_activity_category,
    _validate_category_parent,
)
from app.api.admin_resource_feedback_label import (
    _create_feedback_label,
    _serialize_feedback_label,
    _update_feedback_label,
)
from app.api.admin_resource_location import (
    _create_location,
    _serialize_location,
    _update_location,
    _validate_coordinates,
)
from app.api.admin_resource_organization import (
    _create_organization,
    _serialize_organization,
    _update_organization,
    _update_organization_for_manager,
)
from app.api.admin_resource_pricing import (
    _create_pricing,
    _serialize_pricing,
    _update_pricing,
    _validate_pricing_amount,
    _validate_sessions_count,
)
from app.api.admin_resource_schedule import (
    _create_schedule,
    _serialize_schedule,
    _update_schedule,
    _validate_schedule,
)
from app.db.models import (
    Activity,
    ActivityCategory,
    ActivityPricing,
    ActivitySchedule,
    FeedbackLabel,
    Location,
    Organization,
)
from app.db.repositories import (
    ActivityCategoryRepository,
    ActivityPricingRepository,
    ActivityRepository,
    ActivityScheduleRepository,
    FeedbackLabelRepository,
    LocationRepository,
    OrganizationRepository,
)

__all__ = [
    "_RESOURCE_CONFIG",
    "_create_activity",
    "_create_activity_category",
    "_create_feedback_label",
    "_create_location",
    "_create_organization",
    "_create_pricing",
    "_create_schedule",
    "_serialize_activity",
    "_serialize_activity_category",
    "_serialize_feedback_label",
    "_serialize_location",
    "_serialize_organization",
    "_serialize_pricing",
    "_serialize_schedule",
    "_update_activity",
    "_update_activity_for_manager",
    "_update_activity_category",
    "_update_feedback_label",
    "_update_location",
    "_update_organization",
    "_update_organization_for_manager",
    "_update_pricing",
    "_update_schedule",
    "_validate_age_range",
    "_validate_category_parent",
    "_validate_coordinates",
    "_validate_pricing_amount",
    "_validate_schedule",
    "_validate_sessions_count",
]


_RESOURCE_CONFIG = {
    "organizations": ResourceConfig(
        name="organizations",
        model=Organization,
        repository_class=OrganizationRepository,
        serializer=_serialize_organization,
        create_handler=_create_organization,
        update_handler=_update_organization,
        manager_update_handler=_update_organization_for_manager,
    ),
    "locations": ResourceConfig(
        name="locations",
        model=Location,
        repository_class=LocationRepository,
        serializer=_serialize_location,
        create_handler=_create_location,
        update_handler=_update_location,
    ),
    "activity-categories": ResourceConfig(
        name="activity-categories",
        model=ActivityCategory,
        repository_class=ActivityCategoryRepository,
        serializer=_serialize_activity_category,
        create_handler=_create_activity_category,
        update_handler=_update_activity_category,
    ),
    "feedback-labels": ResourceConfig(
        name="feedback-labels",
        model=FeedbackLabel,
        repository_class=FeedbackLabelRepository,
        serializer=_serialize_feedback_label,
        create_handler=_create_feedback_label,
        update_handler=_update_feedback_label,
    ),
    "activities": ResourceConfig(
        name="activities",
        model=Activity,
        repository_class=ActivityRepository,
        serializer=_serialize_activity,
        create_handler=_create_activity,
        update_handler=_update_activity,
        manager_update_handler=_update_activity_for_manager,
    ),
    "pricing": ResourceConfig(
        name="pricing",
        model=ActivityPricing,
        repository_class=ActivityPricingRepository,
        serializer=_serialize_pricing,
        create_handler=_create_pricing,
        update_handler=_update_pricing,
    ),
    "schedules": ResourceConfig(
        name="schedules",
        model=ActivitySchedule,
        repository_class=ActivityScheduleRepository,
        serializer=_serialize_schedule,
        create_handler=_create_schedule,
        update_handler=_update_schedule,
    ),
}
