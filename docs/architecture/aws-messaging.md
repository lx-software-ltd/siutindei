# AWS Messaging Architecture

## Overview

Ticket submissions are processed asynchronously using SNS + SQS messaging. This provides reliable, decoupled processing with automatic retries and dead letter queue support.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ASYNC TICKET PROCESSING                              │
│                                                                             │
│  User submits ──▶ API Lambda ──▶ SNS Topic ──▶ SQS Queue ──▶ Processor     │
│   ticket               │              │              │         Lambda       │
│                        │              │              │            │         │
│                   (validates,    (fan-out)     (reliable      (stores in   │
│                   returns 202)                  delivery)      DB, sends   │
│                                                    │           email)      │
│                                                    │                       │
│                                                    ▼                       │
│                                               Dead Letter                  │
│                                                 Queue                      │
│                                            (failed messages)               │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Components

### SNS Topic: `lxsoftware-siutindei-manager-request-events`

- Receives ticket events from the API
- Fans out to subscribed SQS queue
- Message attributes enable filtering by `event_type`

### SQS Queue: `lxsoftware-siutindei-manager-request-queue`

- Subscribes to SNS topic
- 60 second visibility timeout (6x Lambda timeout)
- 3 retry attempts before DLQ
- SQS-managed encryption

### Dead Letter Queue: `lxsoftware-siutindei-manager-request-dlq`

- Receives messages that fail processing 3 times
- 14 day retention for debugging
- CloudWatch alarm triggers when messages arrive

### Processor Lambda: `ManagerRequestProcessor`

- Triggered by SQS messages
- Routes each message to the appropriate handler based on `event_type`
- Stores the ticket in the `tickets` table
- Sends email notification via SES
- Idempotent via `ticket_id` check

## Message Format

Each SNS message includes an `event_type` field that determines how the
processor handles it. The `ticket_id` field provides idempotency.

Example:

```json
{
  "event_type": "<type>.submitted",
  "ticket_id": "X00001",
  "...": "type-specific fields"
}
```

Current event types:
- `manager_request.submitted`
- `organization_suggestion.submitted`
- `organization_feedback.submitted`

## API Behavior

User-facing submission endpoints are under `/v1/user/`. Admin review
endpoints are at `/v1/admin/tickets`. For full endpoint details
(parameters, request/response schemas), see the OpenAPI spec:
[`docs/api/admin.yaml`](../api/admin.yaml).

**Processing flow:**
1. User POSTs a submission → API validates, generates ticket ID, publishes to SNS
2. Returns `202 Accepted` with ticket ID
3. SQS delivers message to processor Lambda
4. Processor stores in DB and sends email notification to support

## Error Handling

| Scenario | Behavior |
|----------|----------|
| SNS publish fails | API returns 500, user can retry |
| Processor fails | SQS retries up to 3 times |
| All retries fail | Message moves to DLQ, alarm triggers |
| Email send fails | Logged but doesn't fail processing |

## Idempotency

The processor checks if a ticket with the same `ticket_id` already exists before inserting. This handles SQS's at-least-once delivery guarantee.

## Listing-events rollup

A nightly EventBridge rule (`lxsoftware-siutindei-listing-events-rollup`)
invokes `ListingEventsRollupFunction` at 16:15 UTC. The job deletes and
rebuilds that UTC day's `listing_events_daily` rows from `listing_events`.
Re-runs are idempotent. Manual invoke with `{"day": "YYYY-MM-DD"}`
backfills one day.

## Files

| File | Description |
|------|-------------|
| `backend/infrastructure/lib/api-stack.ts` | CDK infrastructure |
| `backend/src/app/api/admin.py` | API handler with SNS publish |
| `backend/lambda/manager_request_processor/handler.py` | SQS processor |
| `backend/src/app/db/repositories/ticket.py` | Repository with `find_by_ticket_id` |

## Environment Variables

### API Lambda

| Variable | Description |
|----------|-------------|
| `MANAGER_REQUEST_TOPIC_ARN` | SNS topic ARN (required) |
| `FEEDBACK_TOPIC_ARN` | Optional SNS topic ARN for feedback (defaults to manager topic) |

### Processor Lambda

| Variable | Description |
|----------|-------------|
| `DATABASE_SECRET_ARN` | Database credentials secret |
| `DATABASE_PROXY_ENDPOINT` | RDS Proxy endpoint |
| `SUPPORT_EMAIL` | Email to receive notifications |
| `SES_SENDER_EMAIL` | Verified SES sender address |
| `SES_TEMPLATE_NEW_ACCESS_REQUEST` | Optional SES template for access requests |
| `SES_TEMPLATE_NEW_SUGGESTION` | Optional SES template for suggestions |
| `SES_TEMPLATE_NEW_FEEDBACK` | Optional SES template for feedback submissions |

## Stack Outputs

| Output | Description |
|--------|-------------|
| `ManagerRequestTopicArn` | SNS topic ARN |
| `ManagerRequestQueueUrl` | SQS queue URL |
| `ManagerRequestDLQUrl` | Dead letter queue URL |

## Monitoring

- **DLQ Alarm**: Triggers when messages land in DLQ
- **CloudWatch Logs**: Both API and processor Lambda log to CloudWatch
- **X-Ray**: Tracing enabled for request flow visibility
