"""Live catalog rows as compare payloads."""

from __future__ import annotations

from typing import Any

from app.db.models import (
    Activity,
    ActivityPricing,
    ActivitySchedule,
    Location,
    Organization,
)


def organization_payload(org: Organization) -> dict[str, Any]:
    """Fields compared for an organization. Manager id is not one of them."""
    return {
        "name": org.name,
        "description": org.description,
        "name_translations": org.name_translations,
        "description_translations": org.description_translations,
        "phone_country_code": org.phone_country_code,
        "phone_number": org.phone_number,
        "email": org.email,
        "whatsapp": org.whatsapp,
        "facebook": org.facebook,
        "instagram": org.instagram,
        "tiktok": org.tiktok,
        "twitter": org.twitter,
        "xiaohongshu": org.xiaohongshu,
        "wechat": org.wechat,
        "media_urls": list(org.media_urls or []),
        "logo_media_url": org.logo_media_url,
        "place_id": org.place_id,
        "status": org.status,
        "source": org.source,
        "source_id": org.source_id,
        "source_url": org.source_url,
        "source_note": org.source_note,
        "description_source": org.description_source,
        "website": org.website,
    }


def activity_payload(activity: Activity) -> dict[str, Any]:
    """Activity fields. Age stays as the stored range for the shape helper."""
    return {
        "name": activity.name,
        "description": activity.description,
        "name_translations": activity.name_translations,
        "description_translations": activity.description_translations,
        "age_range": activity.age_range,
        "source_url": activity.source_url,
        "source_note": activity.source_note,
        "source_category_name": activity.source_category_name,
    }


def location_payload(location: Location) -> dict[str, Any]:
    """Location fields, with area id as text so it matches a snapshot."""
    return {
        "address": location.address,
        "area_id": str(location.area_id) if location.area_id else None,
        "lat": location.lat,
        "lng": location.lng,
        "place_id": location.place_id,
    }


def pricing_payload(pricing: ActivityPricing, location: Location) -> dict[str, Any]:
    """Pricing fields plus the venue address and identity keys."""
    return {
        "location_address": location.address,
        "pricing_type": pricing.pricing_type,
        "amount": pricing.amount,
        "currency": pricing.currency,
        "sessions_count": pricing.sessions_count,
        "free_trial_class_offered": pricing.free_trial_class_offered,
        "activity_id": str(pricing.activity_id),
        "location_id": str(pricing.location_id),
    }


def schedule_payload(
    schedule: ActivitySchedule,
    location: Location,
) -> dict[str, Any]:
    """Schedule fields plus UTC entries and identity keys."""
    return {
        "location_address": location.address,
        "languages": list(schedule.languages or []),
        "entries": [
            {
                "day_of_week_utc": entry.day_of_week_utc,
                "start_minutes_utc": entry.start_minutes_utc,
                "end_minutes_utc": entry.end_minutes_utc,
            }
            for entry in schedule.entries
        ],
        "activity_id": str(schedule.activity_id),
        "location_id": str(schedule.location_id),
    }
