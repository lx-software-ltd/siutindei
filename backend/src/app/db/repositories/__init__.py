"""Repository pattern implementations for database operations.

Repositories provide a clean abstraction over database operations,
making business logic independent of the persistence layer.
"""

from app.db.repositories.api_key import ApiKeyRepository
from app.db.repositories.base import BaseRepository
from app.db.repositories.geographic_area import GeographicAreaRepository
from app.db.repositories.organization import OrganizationRepository
from app.db.repositories.listing_event import (
    ListingEventRepository,
    ListingEventsDailyRepository,
)
from app.db.repositories.location import LocationRepository
from app.db.repositories.activity import ActivityRepository
from app.db.repositories.activity_category import ActivityCategoryRepository
from app.db.repositories.feedback_label import FeedbackLabelRepository
from app.db.repositories.pricing import ActivityPricingRepository
from app.db.repositories.organization_feedback import OrganizationFeedbackRepository
from app.db.repositories.schedule import ActivityScheduleRepository
from app.db.repositories.ticket import TicketRepository

__all__ = [
    "ApiKeyRepository",
    "BaseRepository",
    "GeographicAreaRepository",
    "OrganizationRepository",
    "ListingEventRepository",
    "ListingEventsDailyRepository",
    "LocationRepository",
    "ActivityRepository",
    "ActivityCategoryRepository",
    "FeedbackLabelRepository",
    "ActivityPricingRepository",
    "OrganizationFeedbackRepository",
    "ActivityScheduleRepository",
    "TicketRepository",
]
