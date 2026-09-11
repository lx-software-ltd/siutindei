# Database Audit Logging

This document describes the audit logging implementation for tracking all data changes in the database.

## Overview

The system uses a **hybrid audit logging approach** combining:

1. **Database Triggers** - Automatically capture all INSERT, UPDATE, DELETE operations
2. **Application-Level Context** - Enriches trigger logs with user identity and request ID

This ensures:
- All changes are captured, even direct database modifications
- Business context (who, why) is preserved with each change
- Compliance with audit requirements

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Lambda Handler                            │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  set_audit_context(session, user_id, request_id)        │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Database Operations (CRUD)                  │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                        PostgreSQL                                │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │           Audit Trigger Function                         │    │
│  │  - Reads app.current_user_id from session               │    │
│  │  - Reads app.current_request_id from session            │    │
│  │  - Captures old/new values as JSONB                     │    │
│  │  - Detects changed fields                               │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    audit_log table                       │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

## Database Schema

### audit_log Table

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `timestamp` | TIMESTAMPTZ | When the change occurred |
| `table_name` | TEXT | Name of the modified table |
| `record_id` | TEXT | Primary key of the modified record |
| `action` | TEXT | INSERT, UPDATE, or DELETE |
| `user_id` | TEXT | Cognito user sub who made the change |
| `request_id` | TEXT | Lambda request ID for log correlation |
| `old_values` | JSONB | Previous values (UPDATE/DELETE) |
| `new_values` | JSONB | New values (INSERT/UPDATE) |
| `changed_fields` | TEXT[] | List of fields that changed (UPDATE) |
| `source` | TEXT | 'trigger' or 'application' |
| `ip_address` | TEXT | Client IP (if available) |
| `user_agent` | TEXT | Client user agent (if available) |

### Indexes

- `audit_log_table_record_idx` - Query history for a specific record
- `audit_log_timestamp_idx` - Query by time range
- `audit_log_user_id_idx` - Query user activity
- `audit_log_action_idx` - Filter by action type

## Usage

### Automatic Trigger-Based Auditing

All CRUD operations on product tables are automatically audited via
database triggers. `listing_events` and `listing_events_daily` are
**not** audited (high-volume telemetry). To include user context:

```python
from sqlalchemy.orm import Session
from app.db.engine import get_engine
from app.db.audit import set_audit_context

with Session(get_engine()) as session:
    # Set context for trigger-based auditing
    set_audit_context(
        session,
        user_id="cognito-user-sub",
        request_id="lambda-request-id"
    )

    # All changes in this transaction will be audited with this context
    repo = OrganizationRepository(session)
    org = repo.get_by_id(org_id)
    org.name = "New Name"
    repo.update(org)
    session.commit()
```

### Application-Level Auditing

For custom actions or additional metadata:

```python
from app.db.audit import AuditService, serialize_for_audit

with Session(get_engine()) as session:
    audit = AuditService(
        session,
        user_id="cognito-user-sub",
        request_id="lambda-request-id",
        ip_address="192.168.1.1",
    )

    # Log a custom action
    audit.log_custom(
        table_name="organization_access_requests",
        record_id=request.id,
        action="APPROVE",
        old_values={"status": "pending"},
        new_values={"status": "approved"},
    )

    session.commit()
```

### Querying Audit Logs

```python
from app.db.audit import AuditLogRepository
from datetime import datetime, timedelta

with Session(get_engine()) as session:
    repo = AuditLogRepository(session)

    # Get history for a specific record
    history = repo.get_record_history("organizations", org_id)

    # Get user activity
    activity = repo.get_user_activity(user_sub, limit=50)

    # Get recent changes to a table
    recent = repo.get_table_activity(
        "activities",
        since=datetime.now() - timedelta(days=7),
        action="DELETE"
    )
```

## Audited Tables

The following tables have audit triggers:

- `organizations`
- `locations`
- `activities`
- `activity_locations`
- `activity_pricing`
- `activity_schedule`
- `organization_access_requests`
- `api_keys` (the `key_hash` field is redacted in admin API responses)

## Performance Considerations

1. **Trigger Overhead**: Minimal (~1-2ms per operation)
2. **Storage Growth**: Monitor `audit_log` table size
3. **Query Performance**: Use indexes for efficient queries

### Recommended Retention Policy

Consider implementing a retention policy to manage audit log growth:

```sql
-- Example: Archive logs older than 1 year
DELETE FROM audit_log
WHERE timestamp < NOW() - INTERVAL '1 year';
```

## Security

- **No PII in logs**: User IDs are Cognito subs, not emails. Writes made
  through the partner API are attributed to `api-key:<key id>`.
- **Request correlation**: Use `request_id` to correlate with CloudWatch logs
- **Access control**: Only admin users can query audit logs via API
- **Tamper evidence**: Trigger-based logging cannot be bypassed by application code

## Compliance

This implementation supports:

- **SOC 2**: Change tracking and accountability
- **GDPR**: Data processing audit trail
- **Internal policies**: Who changed what, when

## Admin API Endpoints

Audit logs can be queried via the admin API at `/v1/admin/audit-logs`.
For full endpoint details (parameters, request/response schemas), see the
OpenAPI spec: [`docs/api/admin.yaml`](../api/admin.yaml) — search for
`/v1/admin/audit-logs`.

**Note:** Sensitive fields (password, secret, token, api_key) are
automatically redacted from `old_values` and `new_values` in API responses.

---

## Migration

The audit logging is added via Alembic migration `0010_add_audit_logging.py`.

To apply:
```bash
cd backend/db
alembic upgrade head
```

To rollback:
```bash
alembic downgrade 0009_rename_owner_to_manager
```
