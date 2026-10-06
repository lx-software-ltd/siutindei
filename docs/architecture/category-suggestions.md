# Category suggestions

Unknown imported category names are captured instead of failing the
organization, then enriched off the request path. Admins approve, map,
or reject each suggestion from the Category Suggestions tab on the
Categories page.

Endpoint shapes live in `docs/api/admin.yaml` under
`/v1/admin/category-suggestions`.

## Capture

Resolution order for `category_name` is exact name, then an alias from
an approved or targeted suggestion, then a unique normalised match on
the English name and `name_translations` (case, whitespace, and
punctuation insensitive). Anything else is captured when
`on_import_enabled` is true. Two categories with the same exact name
are captured too when that switch is on; when it is off, an unknown or
ambiguous name still fails the import.

Captured activities use the system category Pending categorisation
(`c1111111-1111-1111-1111-111111111199`, Chinese name 待分類). Public
search always excludes that category. Organization review adds the
blocker `pending_category`, so an organization cannot be approved
without force while an activity is still pending.

One suggestion exists per normalised name. A rejected suggestion with
no target reopens if the same name is imported again. A target on
approve, map, or reject-with-target is an alias for later imports.
Reject without a target leaves activities on the pending category.
Those activities stay out of search and keep the organization blocked.
The summary reports them as `stranded_activity_total`, and the admin
detail says they still need a map.

Live imports enqueue enrichment when a suggestion is created or
reopened, or when its activity count crosses 5 or 25. Dry runs roll
the suggestion rows back and enqueue nothing.

## OpenRouter

In-VPC Lambdas call OpenRouter only through
`app.services.openrouter_client`, which uses the existing HTTP proxy
(`http_invoke`). `SiutindeiAdminFunction` reads the named key
`lxsoftware:siutindei` from Secrets Manager and sends `Authorization`
when SQS invokes it. The proxy does not store or inject that key.

Requests set `usage.include`, app attribution (`siutindei`, title
"Siu Tin Dei", referer `https://siutindei.com`), and
`provider.data_collection=deny` unless the admin setting disables it.
The default model is `qwen/qwen3-30b-a3b` with fallback
`qwen/qwen-turbo`. Admins change the model on the settings singleton
without a redeploy.

Enrichment runs on `SiutindeiAdminFunction` (120 seconds) and makes
one OpenRouter call of up to 90 seconds. SQS retries that message;
the client does not retry inside the Lambda, because three 90-second
attempts would be killed at the Lambda timeout. A separate worker
function would exceed the CloudFormation 500-resource cap. The admin
"test model" action reads the saved model for that request and is one
attempt of about 15 seconds, because API Gateway REST integrations
time out at 29 seconds.

Prompts redact email addresses and phone numbers. The model is asked
to prefer an existing category, otherwise a sub-category, with a
Traditional Chinese name.

## Settings

`category_suggestion_settings` is a single row. `on_import_enabled`
defaults to false and is the only capture switch. `auto_enrich_enabled`
defaults to true. Model slugs match `vendor/model` and are at most 128
characters. At most three fallbacks are stored. Evidence size is 5 to
50 items, default 25.

Only the admin group can read or change suggestions and settings.
`auto_assign_threshold` defaults to 0.90. Blank disables automatic
reassignment. The allowed range is 0.50 to 1.

## Category check

The Category checks tab scans activities whose organization is still
`pending_review`. The organization filter limits one run to a single
organization; the default is every pending organization. It does not
include approved organizations. A run skips an activity that was
confirmed, applied, or auto-applied in the last 30 days unless the
request sets `rescan`. An activity with a review still `pending` is
skipped even on rescan, so a second run does not open a duplicate
decision. An activity an admin dismissed or reverted is still scanned,
and it is never auto-assigned again. A reassign whose target is the
activity's current category is stored as confirm.

Each batch is one SQS message, `{"scan_run_id", "activity_ids"}`, on
the same queue as enrichment. The model returns confirm, reassign, or
propose. Confirm leaves the category in place. Reassign at or above
the threshold changes `activities.category_id` immediately and stores
the previous category. A lower score, or an organization that left
`pending_review` before the batch ran, stays as a pending review.
Propose finds or creates one `source=scan` suggestion per normalised
name and leaves the assignment to the existing approve or map action.
The checks table does not offer Apply for a proposal or for a confirm
of Pending categorisation, because those rows have no category to
assign. A proposed name that already matches a category becomes a
reassign. Pending categorisation is never confirmed. A partial unique
index allows only one queued or running scan. The summary and run
list mark a run failed when it has had no batch progress for 11
minutes (three 180-second visibility timeouts plus the Lambda
timeout), which also re-enables the scan button. A new run is refused
when this month's category-check spend has reached
`monthly_cost_limit_usd` (default 25). The queue consumer runs at most
two batches at once, because the admin function also serves live
traffic.

Approving or mapping a scan suggestion assigns linked activities whose
review is still pending. Rejecting without a target dismisses those
reviews and leaves the category unchanged. Apply, dismiss, and revert
are `POST /v1/admin/category-suggestions/reviews/{id}`. Revert restores
`previous_category_id`.

A pending review is the organization-review warning
`category_check_pending`. It does not block approval. The scan button
is the only trigger. `scan_candidate_total` is the full candidate
count; a run still stops at `scan_limit` (500).
