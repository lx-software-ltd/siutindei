# Organization Suggestions

This document describes the organization suggestion feature that allows public users to suggest new places for admin review.

## Overview

Public logged-in users can suggest new organizations (places) without becoming managers. This is useful for:
- Users discovering new venues they want to share
- Community-driven content expansion
- Quality control through admin review

## User Flow

```
┌─────────────────┐     ┌─────────────┐     ┌─────────────┐
│   User submits  │────▶│  SNS Topic  │────▶│  SQS Queue  │
│   suggestion    │     │             │     │             │
└─────────────────┘     └─────────────┘     └──────┬──────┘
                                                    │
                                                    ▼
┌─────────────────┐     ┌─────────────┐     ┌─────────────┐
│  Admin reviews  │◀────│  Database   │◀────│   Lambda    │
│  in console     │     │             │     │  Processor  │
└────────┬────────┘     └─────────────┘     └─────────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────┐
│ Approve/Reject  │────▶│ Email sent  │
│                 │     │ to user     │
└─────────────────┘     └─────────────┘
```

## API Endpoints

The organization suggestion feature exposes endpoints under two route
groups:

- **User endpoints** (`/v1/user/organization-suggestion`): Any
  authenticated user can view their suggestion history and submit new
  suggestions.
- **Admin review** (`/v1/admin/tickets`): Suggestions are tickets with
  `ticket_type = 'organization_suggestion'`. Admins list and decide
  them through the tickets route.

For full endpoint details (parameters, request/response schemas,
authentication requirements), see the OpenAPI spec:
[`docs/api/admin.yaml`](../api/admin.yaml) — search for
`/v1/user/organization-suggestion` and `/v1/admin/tickets`.

## Database Schema

Organization suggestions are stored in the **`tickets`** table with
`ticket_type = 'organization_suggestion'`. Type-specific columns
(description, district, address, coordinates, media) are populated
for suggestion tickets.

See `docs/architecture/database-schema.md` for the full `tickets` table schema.

## Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `SUGGESTION_TOPIC_ARN` | SNS topic for suggestions (or uses `MANAGER_REQUEST_TOPIC_ARN`) |
| `SES_SENDER_EMAIL` | Email sender for notifications |
| `SES_TEMPLATE_NEW_SUGGESTION` | Optional SES template for new suggestions |
| `SES_TEMPLATE_SUGGESTION_DECISION` | Optional SES template for decision emails |

## Differences from Access Requests

| Feature | Access Request | Organization Suggestion |
|---------|----------------|------------------------|
| **Purpose** | User wants to manage an org | User informs about a new place |
| **User becomes manager** | Yes | No |
| **Ticket prefix** | R (R00001) | S (S00001) |
| **Creates org on approval** | Optional | Optional |
| **Manager assignment** | User becomes manager | Admin becomes temporary manager |
| **Review state** | New organization starts `pending_review` | New organization starts `pending_review` |

## Migration

Schema changes follow `.cursor/skills/db-migration/SKILL.md`.
