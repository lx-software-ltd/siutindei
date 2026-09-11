# Database Schema

This document describes the PostgreSQL schema for the activities
backend. It is based on the SQLAlchemy models and Alembic migrations.

Alembic migrations live in `backend/db/alembic/versions/`.
Seed data lives in `backend/db/seed/seed_data.sql`.

## Extensions and enums

- Extension: `pgcrypto` (used by `gen_random_uuid()` defaults).
- Enum `pricing_type`: `per_class`, `per_sessions`, `per_hour`, `per_day`,
  `free`.
- Enum `schedule_type`: `weekly`.
- Enum `ticket_type`: `access_request`, `organization_suggestion`.
- Enum `ticket_status`: `pending`, `approved`, `rejected`.

## Table: organizations

Purpose: Organizations that provide activities.

Columns:
- `id` (UUID, PK, default `gen_random_uuid()`)
- `name` (text, required)
- `description` (text, optional)
- `name_translations` (jsonb, default `{}`) — non-English name translations
- `description_translations` (jsonb, default `{}`) — non-English description translations
- `manager_id` (text, required) — Cognito user sub of the organization manager
- `phone_country_code` (text, optional) — ISO 3166-1 alpha-2 country code
- `phone_number` (text, optional) — national phone number digits
- `email` (text, optional)
- `whatsapp` (text, optional)
- `facebook` (text, optional)
- `instagram` (text, optional)
- `tiktok` (text, optional)
- `twitter` (text, optional)
- `xiaohongshu` (text, optional)
- `wechat` (text, optional)
- `media_urls` (text[], default empty array)
- `logo_media_url` (text, optional)
- `created_at` (timestamptz, default `now()`)
- `updated_at` (timestamptz, default `now()`)

Relationships:
- One organization has many locations.
- One organization has many activities.

Constraints:
- UNIQUE (case-insensitive) on `lower(trim(name))`

## Table: geographic_areas

Purpose: Hierarchical lookup of valid geographic areas (country > region > city > district).

Hong Kong uses four `level=region` nodes (Hong Kong Island, Kowloon, New Territories,
Islands) between the `HK` country row and the 18 district rows. Home wizard region
choices reference these region UUIDs; search matches any descendant district.

Columns:
- `id` (UUID, PK, default `gen_random_uuid()`)
- `parent_id` (UUID, FK -> geographic_areas.id, cascade delete, nullable for countries)
- `name` (text, required)
- `name_translations` (jsonb, default `{}`) — non-English name translations
- `level` (text, required — `country`, `region`, `city`, or `district`)
- `code` (text, optional — ISO 3166-1 alpha-2 for countries)
- `active` (boolean, default true — controls country visibility)
- `display_order` (integer, default 0)

Constraints:
- UNIQUE(`parent_id`, `name`)

Indexes:
- `geo_areas_parent_idx` on `parent_id`
- `geo_areas_level_idx` on `level`
- `geo_areas_code_idx` on `code`

## Table: activity_categories

Purpose: Hierarchical lookup of activity categories.

Columns:
- `id` (UUID, PK, default `gen_random_uuid()`)
- `parent_id` (UUID, FK -> activity_categories.id, nullable for roots)
- `name` (text, required)
- `name_translations` (jsonb, default `{}`) — non-English name translations
- `display_order` (integer, default 0)

Constraints:
- UNIQUE(`parent_id`, `name`)

Indexes:
- `activity_categories_parent_idx` on `parent_id`
- `activity_categories_name_idx` on `name`

## Table: locations

Purpose: Physical or logical locations for an organization.

Columns:
- `id` (UUID, PK, default `gen_random_uuid()`)
- `org_id` (UUID, FK -> organizations.id, cascade delete)
- `area_id` (UUID, FK -> geographic_areas.id, required)
- `address` (text, optional)
- `lat` (numeric(9,6), optional)
- `lng` (numeric(9,6), optional)
- `created_at` (timestamptz, default `now()`)
- `updated_at` (timestamptz, default `now()`)

Indexes:
- `locations_district_idx` on `district`
- `locations_org_idx` on `org_id`
- `locations_area_idx` on `area_id`

Constraints:
- UNIQUE (case-insensitive) on (`org_id`, `lower(trim(address))`)

## Table: activities

Purpose: Activities offered by organizations.

Columns:
- `id` (UUID, PK, default `gen_random_uuid()`)
- `org_id` (UUID, FK -> organizations.id, cascade delete)
- `category_id` (UUID, FK -> activity_categories.id, restrict delete)
- `name` (text, required)
- `description` (text, optional)
- `name_translations` (jsonb, default `{}`) — non-English name translations
- `description_translations` (jsonb, default `{}`) — non-English description translations
- `age_range` (int4range, required)
- `created_at` (timestamptz, default `now()`)
- `updated_at` (timestamptz, default `now()`)

Indexes:
- `activities_age_gist` on `age_range` (GiST)
- `activities_org_idx` on `org_id`
- `activities_category_idx` on `category_id`

Constraints:
- UNIQUE (case-insensitive) on (`org_id`, `lower(trim(name))`)

## Table: activity_locations

Purpose: Join table for activities and locations.

Columns:
- `activity_id` (UUID, PK, FK -> activities.id, cascade delete)
- `location_id` (UUID, PK, FK -> locations.id, cascade delete)

Indexes:
- `activity_locations_location_idx` on `location_id`

## Table: activity_pricing

Purpose: Pricing for an activity at a location.

Columns:
- `id` (UUID, PK, default `gen_random_uuid()`)
- `activity_id` (UUID, FK -> activities.id, cascade delete)
- `location_id` (UUID, FK -> locations.id, cascade delete)
- `pricing_type` (enum `pricing_type`, required)
- `amount` (numeric(10,2), required)
- `currency` (text, default `HKD`)
- `sessions_count` (integer, optional)
- `free_trial_class_offered` (boolean, default `false`)

Constraints:
- `pricing_sessions_count_check`:
  `sessions_count` is required and > 0 when
  `pricing_type = 'per_sessions'`.

Indexes:
- `activity_pricing_type_amount_idx` on `pricing_type`, `amount`
- `activity_pricing_location_idx` on `location_id`

## Table: activity_schedule

Purpose: Weekly schedule definitions for an activity at a location.

Columns:
- `id` (UUID, PK, default `gen_random_uuid()`)
- `activity_id` (UUID, FK -> activities.id, cascade delete)
- `location_id` (UUID, FK -> locations.id, cascade delete)
- `schedule_type` (enum `schedule_type`, required)
- `languages` (text[], default empty array)

Constraints:
- `schedule_type_weekly_only`: schedule_type must be `weekly`
- `schedule_unique_activity_location_languages`: unique on (`activity_id`,
  `location_id`, `languages`)

Indexes:
- `activity_schedule_languages_gin` on `languages` (GIN)

## Table: activity_schedule_entries

Purpose: Weekly schedule entries associated with a schedule definition.

Columns:
- `id` (UUID, PK, default `gen_random_uuid()`)
- `schedule_id` (UUID, FK -> activity_schedule.id, cascade delete)
- `day_of_week_utc` (smallint, required, 0=Sunday)
- `start_minutes_utc` (integer, required, minutes after midnight)
- `end_minutes_utc` (integer, required, minutes after midnight)

Constraints:
- `schedule_entry_day_range`: 0 to 6
- `schedule_entry_start_minutes_range`: 0 to 1439
- `schedule_entry_end_minutes_range`: 0 to 1439
- `schedule_entry_minutes_order`: start and end must differ
- `schedule_entry_unique`: unique on (`schedule_id`, `day_of_week_utc`,
  `start_minutes_utc`, `end_minutes_utc`)

Indexes:
- `activity_schedule_entries_schedule_idx` on `schedule_id`
- `activity_schedule_entries_day_idx` on
  `day_of_week_utc`, `start_minutes_utc`, `end_minutes_utc`

## Table: organizations (migration notes)

The following columns were added/renamed after the initial schema:

- `media_urls` was originally named `picture_urls` (renamed in migration 0006)
- `manager_id` was originally named `owner_id` (renamed in migration 0009)

## Table: tickets

Purpose: User-submitted tickets for admin review. The `ticket_type`
column determines the workflow; optional columns are populated as
needed by each type.

Columns:
- `id` (UUID, PK, default `gen_random_uuid()`)
- `ticket_id` (text, unique, required) — progressive ID (prefix + 5 digits)
- `ticket_type` (enum `ticket_type`, required) — workflow discriminator
  (`access_request`, `organization_suggestion`, `organization_feedback`)
- `submitter_id` (text, required) — Cognito user sub
- `submitter_email` (text, required)
- `organization_name` (text, required)
- `message` (text, optional) — free-text from submitter
- `status` (enum `ticket_status`, default `pending`)
- `created_at` (timestamptz, default `now()`)
- `updated_at` (timestamptz, default `now()`)
- `reviewed_at` (timestamptz, optional)
- `reviewed_by` (text, optional) — Cognito user sub of reviewer
- `admin_notes` (text, optional)
- `description` (text, optional)
- `suggested_district` (text, optional)
- `suggested_address` (text, optional)
- `suggested_lat` (numeric, optional)
- `suggested_lng` (numeric, optional)
- `media_urls` (text[], default empty array)
- `organization_id` (UUID, FK -> organizations.id, optional)
- `feedback_stars` (smallint, optional, 0-5)
- `feedback_label_ids` (UUID[], default empty array)
- `feedback_text` (text, optional)
- `created_organization_id` (UUID, FK -> organizations.id, optional)

Indexes:
- Unique on `ticket_id`
- Index on `ticket_type`
- Index on `status`
- Index on `submitter_id`
- Index on `created_at`
- Composite index on (`ticket_type`, `status`)

## Table: feedback_labels

Purpose: Managed list of labels that users can apply to feedback.

Columns:
- `id` (UUID, PK, default `gen_random_uuid()`)
- `name` (text, required)
- `name_translations` (jsonb, default empty object)
- `display_order` (integer, default 0)
- `created_at` (timestamptz, default `now()`)
- `updated_at` (timestamptz, default `now()`)

Indexes:
- Unique index on `lower(trim(name))`
- Index on `display_order`

## Table: organization_feedback

Purpose: Approved feedback entries for organizations.

Columns:
- `id` (UUID, PK, default `gen_random_uuid()`)
- `organization_id` (UUID, FK -> organizations.id, required)
- `submitter_id` (text, optional) — Cognito user sub
- `submitter_email` (text, optional)
- `stars` (smallint, required, 0-5)
- `label_ids` (UUID[], default empty array)
- `description` (text, optional)
- `source_ticket_id` (text, optional)
- `created_at` (timestamptz, default `now()`)
- `updated_at` (timestamptz, default `now()`)

Indexes:
- Index on `organization_id`
- Index on `submitter_id`
- Index on `created_at`
- GIN index on `label_ids`

## Table: api_keys

Purpose: Partner API keys for the `/v1/partner/*` endpoints. Only SHA-256
hashes are stored; plaintext keys are shown once at creation.

Columns:
- `id` (UUID, PK, default `gen_random_uuid()`)
- `name` (text, required) — human-readable label
- `key_prefix` (text, required) — first characters of the plaintext key, for display
- `key_hash` (text, required, unique) — SHA-256 hex digest of the plaintext key
- `scope` (text, required, CHECK in `read`, `crud`)
- `org_id` (UUID, FK -> organizations.id ON DELETE CASCADE, optional) —
  restricts the key to one organization; NULL = full access
- `created_by` (text, optional) — Cognito sub of the creating admin
- `created_at` (timestamptz, default `now()`)
- `expires_at` (timestamptz, optional) — NULL = does not expire
- `revoked_at` (timestamptz, optional) — set on revoke; NULL = active
- `last_used_at` (timestamptz, optional)

Indexes:
- Unique index on `key_hash`
- Index on `org_id`

Grants:
- `siutindei_app`: SELECT plus column-scoped UPDATE on `last_used_at`
  (used by the partner API-key authorizer)
- `siutindei_admin`: SELECT, INSERT, UPDATE, DELETE

Audited via `api_keys_audit_trigger` (the `key_hash` field is redacted in
admin audit-log responses).

## Table: listing_events

Purpose: First-party listing funnel events from public www (and later
Flutter). The Executive Board already reads GA4 via its `web` tools;
this table is the location-grained product source for
`listing_events_daily` / `v_funnel_daily`.

Columns:
- `id` (UUID, PK, default `gen_random_uuid()`)
- `occurred_on` (date, required) — UTC day used by the nightly rollup
- `occurred_at` (timestamptz, default `now()`)
- `event_type` (text, required — `search`, `listing_view`, `cta_tap`,
  `lead_relayed`)
- `location_id` (UUID, required, default nil UUID) — venue; nil UUID
  for unattributed searches and site-wide CTAs
- `activity_id` (UUID, optional)
- `source` (text, required — `public_www`, `flutter`, `partner`)
- `client_event_id` (text, required) — client idempotency key
- `created_at` (timestamptz, default `now()`)

Indexes:
- `listing_events_day_type_idx` on (`occurred_on`, `event_type`,
  `location_id`)
- Unique `listing_events_client_id_uniq` on (`source`,
  `client_event_id`)

Grants:
- `siutindei_admin`: SELECT, INSERT

Not audited: high-volume telemetry. Do not store search terms, names,
or other PII.

## Table: listing_events_daily

Purpose: Daily listing funnel counts by location. The lx-software
`v_funnel_daily` view aggregates this table by district. The admin
stack may create the table first (`CREATE TABLE IF NOT EXISTS`); the
product migration adopts the same shape and owns the writer.

Columns:
- `day` (date, PK)
- `location_id` (UUID, PK, default nil UUID)
- `searches` (integer, default 0)
- `listing_views` (integer, default 0)
- `cta_taps` (integer, default 0)
- `leads_relayed` (integer, default 0)
- `bookings_confirmed` (integer, default 0) — stays 0 until a booking
  product exists

Grants:
- `siutindei_admin`: SELECT, INSERT, UPDATE, DELETE

A nightly EventBridge job rebuilds one UTC day from `listing_events`.

## Table: audit_log

Purpose: Automatic change tracking for all audited tables.
Populated via database triggers (see [`audit-logging.md`](audit-logging.md)).

Columns:
- `id` (UUID, PK, default `gen_random_uuid()`)
- `timestamp` (timestamptz, default `now()`)
- `table_name` (text, required)
- `record_id` (text, required) — primary key of the modified record
- `action` (text, required) — INSERT, UPDATE, or DELETE
- `user_id` (text, optional) — Cognito user sub from session context
- `request_id` (text, optional) — Lambda request ID
- `old_values` (jsonb, optional)
- `new_values` (jsonb, optional)
- `changed_fields` (text[], optional)
- `source` (text, optional) — 'trigger' or 'application'
- `ip_address` (text, optional)
- `user_agent` (text, optional)

Indexes:
- `audit_log_table_record_idx` on `table_name`, `record_id`
- `audit_log_timestamp_idx` on `timestamp`
- `audit_log_user_id_idx` on `user_id`
- `audit_log_action_idx` on `action`
