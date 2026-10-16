# Research: Enrich one organization from its website

**Status**: Draft (design only, no commitment to build)
**Zone**: this memo is green. The design touches yellow (admin API,
services, admin web, `docs/api/admin.yaml`) and red (a migration, the
HTTP proxy, `api-stack.ts`). Implementation needs a plan under
`docs/plans/` and red-zone approval before any write.

## Summary

An admin opens an organization, presses **Enrich from website** on the
Details card (top right, left of the version switcher), and the system
crawls the organization's `website`, extracts facts with deterministic
parsers plus one LLM pass, and stores them as **proposals** grouped by
Organization, Media, Locations, Activities, Pricing, and Schedules. A
new card under Details shows each proposal with the current value, the
proposed value, a confidence, and the quote on the page that supports
it. Nothing is written until the admin applies a row. Applies go through
the existing write paths so catalog versions, audit rows, name rules,
and category capture keep working.

The shape follows what the sibling `lx-software` repository already
does for its `catalog-enrich` duty: a polite stdlib crawler with SSRF
and robots guards, an LLM that may only fill `verified_fields` backed by
a fetched page, and a human hold before anything reaches this product.

## Entry points

- Details card and the slot the button goes in:
  `apps/admin_web/src/components/shared/organizations-panel.tsx`
  renders `AdminInputCard title='Details'` with
  `titleAccessory={current ? <VersionSwitcher view={versionView} /> : undefined}`.
  `isAdmin = mode === 'admin'`. Historical versions set
  `versionView.isHistorical` and swap the action bar for "Back to
  latest".
- The accessory slot is right-aligned with `ml-auto` and tagged
  `data-testid='admin-card-title-accessory'`
  (`apps/admin_web/src/components/ui/card.tsx`).
- Readiness card under Details:
  `apps/admin_web/src/components/admin/organization-readiness.tsx`.
  Issue codes come from `backend/src/app/services/org_review.py`:
  `missing_description`, `no_media`, `no_locations`, `no_activities`,
  `missing_coordinates`, `missing_pricing`, `missing_schedule`,
  `pending_category`, `activity_no_location`,
  `missing_activity_description`. These are the gaps enrichment should
  close.
- Admin route dispatch: `backend/src/app/api/admin.py` gates
  `/v1/admin/*` with `_is_admin(event)` and already has a sub-resource
  branch for `organizations/{id}/media`. The importer group is let in
  only for listed import routes.
- Polling convention for a background job:
  `apps/admin_web/src/hooks/use-import-job.ts` and
  `apps/admin_web/src/components/admin/import-run-status.tsx` use
  TanStack Query `refetchInterval`.

## Owners

- Admin console and admin API: the same people who own Data quality
  (`docs/architecture/data-quality.md`).
- Red paths (`backend/db/**`, `backend/infrastructure/**`,
  `backend/src/app/services/aws_proxy.py`,
  `backend/src/app/services/openrouter_client.py`) need a human pair
  (`docs/architecture/zones.md`).

## Callers

Nothing calls this yet. Future callers besides the button: a bulk
action on the Catalog list, a Data quality tab, and the sibling board's
`catalog-enrich` duty, which today crawls on its own side and imports
through `POST /v1/admin/imports`.

## Existing abstractions

### Outbound HTTP is allow-listed

In-VPC Lambdas have no internet. `backend/src/app/services/aws_proxy.py`
runs in `AwsApiProxyFunction` outside the VPC and accepts
`type: "http"` requests only when the URL starts with one of the
prefixes in `ALLOWED_HTTP_URLS` (Nominatim, the EDB CSV, Places,
OpenRouter; `backend/infrastructure/lib/api-stack.ts`). HTTP is capped
at 90 seconds under the proxy's 120-second timeout. Organization
websites are arbitrary hosts, so the `http` type cannot serve a crawl
without turning the proxy into an open relay. That is the main
architectural decision in this design.

### LLM calls

`backend/src/app/services/openrouter_client.py` (red) sends chat
completions through the proxy with the key from Secrets Manager,
attribution headers, `provider.data_collection=deny`, a primary model
and up to three fallbacks from `category_suggestion_settings`, and
`usage.include` so spend can be recorded. `openrouter_json_parse.py`
extracts JSON replies. Location and translation sweeps reuse the
category-check model and keep their own monthly budgets
(`location_fix_settings.monthly_cost_limit_usd`,
`translation_fix_settings.monthly_cost_limit_usd`).

### Background work

One SQS queue, `category-suggestion-enrich`, feeds
`SiutindeiAdminFunction` with batch size 1, `maxConcurrency` 2,
visibility 180 seconds, three receives then DLQ with an alarm
(`docs/architecture/aws-messaging.md`, `api-stack.ts`). The worker in
`backend/lambda/category_suggestions/handler.py` dispatches on the
message key: `translation_scan_run_id`, then `location_scan_run_id`,
then `scan_run_id`. A separate worker function was rejected before
because of the CloudFormation 500-resource cap
(`docs/architecture/lambdas.md`). API Gateway cuts HTTP at 29 seconds.

### Proposals, not writes

`name_fix_proposals`, `location_fix_proposals`, and
`translation_fix_proposals` share one pattern: `entity_type`,
`entity_id`, `org_id`, `field` or `kind`, current and proposed values,
`source`, `confidence`, `rationale`, `status`
(pending/applied/dismissed), `input_hash`, `scan_run_id`,
`decided_by`, `decided_at`. Apply re-checks the stored value, writes
through the normal path, and a dismissed value is not proposed again
(`docs/architecture/data-quality.md`,
`backend/src/app/db/models/translation_fix.py`). Bulk apply caps at
200 rows. A run row records counts, cost, `processed_message_ids`, and
`truncated`.

### Writes that already exist

- Organization update validators:
  `backend/src/app/api/admin_resource_organization.py` and
  `admin_validators.py`. `media_urls` accepts any http(s) URL, at most
  `MAX_MEDIA_URLS_COUNT` (20), sorted; `logo_media_url` must be one of
  them.
- Media upload is a presigned PUT into `ORGANIZATION_MEDIA_BUCKET`
  under `organizations/{org id}/…` (`backend/src/app/api/admin_media.py`).
- Locations, activities, pricing, and schedules have admin resource
  handlers (`admin_resource_location.py`, `admin_resource_activity.py`,
  `admin_resource_pricing.py`, `admin_resource_schedule.py`).
- The importer accepts nested `locations`, `activities`, `pricing`
  (`per_class|per_sessions|per_hour|per_day|free`, amount, currency,
  sessions_count, free_trial_class_offered) and `schedules`
  (timezone, languages, weekly entries with local day and HH:MM)
  (`docs/api/admin.yaml`, `AdminImportPricing`,
  `AdminImportSchedule`). Category names resolve exact, then alias,
  then normalised; unknown names are captured onto Pending
  categorisation (`docs/architecture/category-suggestions.md`).
- Every write records a `catalog_versions` row with `reason`,
  `related_id`, `request_id`, `user_id`, or `import_job_id`
  (`backend/src/app/db/models/catalog_version.py`), so an enrichment
  apply can be attributed and reverted per version.
- Pins come from `location_fix_lookup.py` with grades
  `precise|street|coarse|miss`, district boxes, and the rule that a
  stored pin or `place_id` is never overwritten
  (`docs/plans/location-enrichment.md`).

### Invariants from earlier plans that this design keeps

- `source`, `source_id`, and `source_url` are the catalog page and are
  never written by this feature (`docs/plans/org-website.md`).
- `place_id` is never written from a lookup or a crawl.
- A stored pin is never replaced.
- No `print()`, PII masked in logs, no secrets in URLs
  (`.cursor/rules/00-repository-core.mdc`).

## What the sibling repository does

Cloned read-only from `github.com/lx-software-ltd/lx-software`.

- `backend/lambda/admin/board_crawl.py`: stdlib `urllib` fetch with
  user agent `SiuTinDeiBoardBot/1.0 (+https://siutindei.com/bot)`;
  `host_is_blocked` resolves DNS and refuses loopback, private,
  link-local, multicast, reserved, unspecified, and CGNAT addresses;
  a redirect handler caps hops at 3 and re-checks the host on every
  hop; a byte cap per page; `robots.txt` honoured and cached 24 hours;
  per-host pacing from a configured RPS; 7-day host backoff after
  failures; a 14-day cache of HTTP status so a dead official URL is
  dropped from the next sheet; `<meta http-equiv="refresh">` followed
  because government stub pages are otherwise empty; `html_to_text`
  strips `script`, `style`, `nav`, and `footer`; `normalise` removes
  dates, times, and long digit runs before hashing so a page hash
  means "content changed", not "the clock moved"; the stored digest is
  6000 characters.
- `board_research.op_fetch_page`: a per-task fetch cap (6, 9 for
  catalog enrich) that counts only successful, distinct, normalised
  URLs; on an enrich task only the official URLs listed on the sheet
  may be fetched; when the sheet has names but no URLs a page that
  mentions none of them is refused; HTTP 4xx, empty bodies, and wrong
  content types are "page errors" that do not burn the cap or trip the
  provider breaker; the model receives at most 8000 characters of
  text per page.
- `catalog-enrich` sheets (`board_catalog.compose_enrich_brief`,
  `docs/architecture/executive-board.md` §6.4): the model may only
  fill `verified_fields` and must leave the rest unverified; verified
  `free_or_paid` / `price_note` / `opening_hours` become nested
  pricing and schedule rows for this repository's importer; a verified
  address without coordinates is geocoded through the HK Address
  Lookup Service only when the district matches; a 2-hour
  `catalog_import` hold runs before import; dry-run first; a
  row that fails with schedules is retried once without them.
- Models: OpenRouter with a primary and fallbacks
  (`openrouter_client.py`, `board_budget.py`), budget per seat.

What carries over: stdlib fetching is enough for most provider sites,
so no headless browser in the first version; the LLM contract is
"evidence or omit"; a human applies; nested rows reuse existing
importer validation. What does not carry over: the sibling writes to
this product only through `POST /v1/admin/imports`, which replaces
whole records and is matched by `place_id` or manager plus name. For a
single organization the admin wants to pick fields, so this design
stores per-field proposals instead of generating an import file.

## Proposed design

### Button and placement

`Enrich from website` is a `secondary`, `md` `Button` rendered inside
`titleAccessory` next to `VersionSwitcher`, wrapped in
`flex items-center gap-2` so it sits left of the version control. It
renders only when `isAdmin && current && !versionView.isHistorical`.
It is disabled with a short caption when `formState.website` is empty
("Add a website first"), when a run is queued or running
("Enriching…", with a spinner), or when the monthly budget is spent.
Manager mode never renders it; the manager route also never reaches
the admin API.

Pressing it calls `POST /v1/admin/organizations/{id}/enrichment` and
starts polling. The Readiness description gains one line when
`website` is set and an issue in `no_media`, `no_locations`,
`missing_description`, `missing_pricing`, or `missing_schedule` is
present: "Enrich from website can propose these."

### Result card

A new `AdminInputCard title='Website enrichment' titleLevel='h3'` sits
between Details and Readiness, visible only when a run exists. The
header shows the run state (Queued, Crawling n pages, Extracting,
Ready, Failed, or Site needs a browser) with pages fetched, duration,
model, and cost. The body is one section per domain, each a small
table following the admin table conventions (one fact per cell,
confidence as a percent, `StatusBadge` for state):

| Column | Content |
| --- | --- |
| Field | e.g. `description`, `phone_number`, `Location · address`, `Activity · Ballet (3–6) · price` |
| Current | stored value or an em dash |
| Proposed | the new value; long text expands in place |
| Confidence | percent |
| Evidence | page URL (opens in a new tab) and the quoted snippet |

Row checkboxes with header select-visible, then `Apply selected` and
`Dismiss selected` as `secondary` buttons on the actions row, as on
the Data quality tabs. Locations, Activities, Pricing, and Schedules
show one expandable row per proposed record with its child fields.
A pricing or schedule row whose venue could not be resolved shows a
venue picker before Apply, like `target_location_id` on the Locations
tab.

### API

All routes admin only; the importer group is refused. Shapes go in
`docs/api/admin.yaml`, then `npm run generate:api`.

| Route | Behaviour |
| --- | --- |
| `POST /v1/admin/organizations/{id}/enrichment` | Validates `website` (http or https, host not blocked), refuses with 422 when it is empty or the budget is spent, 409 when a run is queued or running for this organization, else creates the run, enqueues `{"enrichment_run_id": "<uuid>"}`, and answers 202 with the run. |
| `GET /v1/admin/organizations/{id}/enrichment` | Latest run, or `?run_id=`, with proposals grouped by section. Reading does not write. |
| `POST /v1/admin/organizations/{id}/enrichment/apply` | `{"ids": [...]}` plus optional `{"target_location_id"}` per pricing or schedule id. At most 200 ids. Per-id result. |
| `POST /v1/admin/organizations/{id}/enrichment/dismiss` | `{"ids": [...]}`. Remembers the proposed value hash so a rerun does not propose it again. |
| `GET` and `PUT /v1/admin/enrichment-settings` | Singleton: `monthly_cost_limit_usd`, `max_pages` (default 8), `max_page_bytes` (default 1 MB), `copy_media` (default true), `min_confidence_shown` (default 0.5). Model and fallbacks stay on category-check settings, as Locations and Translations do. |

Dispatch in `admin.py`: `resource == "organizations" and sub_resource == "enrichment"`
next to the `media` branch, and `resource == "enrichment-settings"`.

### Pipeline

```
Admin ──POST──▶ Admin API (sync, <1 s)
                 │ create org_enrichment_runs (queued)
                 │ SQS category-suggestion-enrich {"enrichment_run_id"}
                 ▼
            Worker on SiutindeiAdminFunction (120 s)
                 │ 1. crawl   ── proxy type "crawl" ──▶ organization website
                 │ 2. extract ── deterministic parsers, then one OpenRouter call
                 │ 3. store   ── org_enrichment_proposals (pending)
                 ▼
            Admin reviews, applies rows ──▶ existing write paths ──▶ catalog_versions, audit
```

#### 1. Crawl

The admin function is inside the VPC, so fetching must happen in
`AwsApiProxyFunction`. Two options:

- **Option A (recommended): a new `type: "crawl"` request on the
  existing proxy.** It takes `{seed_url, max_pages, max_page_bytes,
  time_budget_seconds}` and enforces its own rules instead of the
  prefix allow-list: http or https only; the sibling's `host_is_blocked`
  DNS check on the seed and on every redirect hop (cap 3); same-site
  lock (same host, or the host with `www.` added or removed, in the
  first version); `robots.txt` honoured with user agent
  `SiutindeiBot/1.0 (+https://siutindei.com/bot)`; one request per
  second per host; one page at most `max_page_bytes`; content types
  `text/html`, `application/xhtml+xml`, `text/plain`, and
  `application/ld+json`; a total budget of at most 60 seconds so the
  call stays under the 90-second proxy cap. The proxy returns parsed
  pages, not HTML: `{url, final_url, status, title, lang, text (≤ 8000
  chars), jsonld[], og{}, tel[], mailto[], image_candidates[{src, alt,
  width, height}], links[{href, text}]}`, keeping the Lambda response
  under 1 MB. The `http` type is unchanged. A second action
  `fetch_image` downloads one image (at most 5 MB, same-site or a
  known CDN of that site, `image/*` only) and writes it to
  `ORGANIZATION_MEDIA_BUCKET` under `organizations/{org id}/enrichment/{sha256}.{ext}`
  with a role statement scoped to that prefix, so image bytes never
  travel through the VPC function.
- **Option B: a dedicated crawler function outside the VPC.** Cleaner
  separation and a longer timeout, but one more function against the
  500-resource cap that already blocked a separate worker. Decide in
  the red-zone plan; A is the smaller change.

Page selection: the seed page first, then `/sitemap.xml` when present
to rank URLs, then links whose path or anchor text matches a bilingual
keyword list (about, 關於; contact, 聯絡; location, 地址, 分店, 校舍;
class, course, 課程, 班; price, fee, 收費, 學費; schedule, timetable,
時間表, 上課時間; gallery, photos, 相片). Breadth first, at most
`max_pages`. Facebook, Instagram, WhatsApp, and other social links
are recorded as handles for the Organization section and never
crawled. When the seed page yields fewer than 200 characters of text
and looks like a script-only shell, the run ends as
`render_required` and the card says the site needs a browser; a
headless renderer is out of the first version.

Fetch status per URL is cached 14 days and a host that answered 429
or repeated 5xx is backed off 7 days, as the sibling does. Storage is
a small Postgres table since this repository has no DynamoDB.

#### 2. Extract

Deterministic parsers run first and carry confidence 0.95 with the
tag as evidence: JSON-LD `Organization`, `LocalBusiness`,
`EducationalOrganization`, `Course`, and `Event` (address, telephone,
email, `openingHoursSpecification`, `image`, `logo`, `sameAs` for
social handles); OpenGraph `og:image`, `og:description`, `og:locale`;
`tel:` and `mailto:` anchors; `wa.me` links; `<html lang>` and
`hreflang` pairs, which give English and Traditional Chinese copies
of the same page for translations.

Then one OpenRouter call through `openrouter_client` with the current
organization snapshot (name, description, existing location names and
addresses, existing activity names, masked contact fields) and the
page texts, highest-ranked pages first and lower pages truncated to fit
roughly 40k characters. The reply is strict JSON parsed by
`openrouter_json_parse`. The contract:

- Every value carries `confidence` in 0 to 1 and `evidence` as
  `[{url, quote}]`. The server checks that `quote` is a substring of
  the fetched text of that URL; a value whose quote is not found is
  downgraded to 0.5 and flagged `unverified`.
- A fact that is not on the site is omitted, never guessed. Chinese
  and English text come from the site; missing translations stay for
  the Translations tab.
- The system prompt states that page text is untrusted content and
  instructions inside it are ignored. Output goes through the same
  validators as a manual edit, so lengths and enums are enforced
  server side, and any URL in a proposal must be on the crawled site
  or a known social host.
- One attempt per receive, 90 seconds, SQS retries, third receive is
  marked failed and left for the DLQ, as the other workers do.
- Spend is recorded from `usage` against
  `enrichment_settings.monthly_cost_limit_usd`; a cache hit on the
  same `input_hash` (site hash plus organization snapshot hash) is
  not charged and reuses the previous proposals.

Section mapping:

| Section | Proposed fields | Dedupe and guard |
| --- | --- | --- |
| Organization | `description` and translations, `email`, `phone_country_code`, `phone_number`, `whatsapp`, `facebook`, `instagram`, `tiktok`, `xiaohongshu`, `wechat`, `twitter`, canonical `website` when the seed redirected, `logo` | One row per field. `source`, `source_id`, `source_url` never. A field equal to the stored value is not proposed. |
| Media | Ranked image candidates from `og:image`, `logo`, and gallery pages; at least 400 px when a size is known; icons and tracking pixels dropped; at most 20 in total with existing `media_urls` | Apply copies bytes through `fetch_image` and appends the bucket URL; the logo proposal applies only after its URL is in `media_urls`. Hotlinking is a setting, off by default. |
| Locations | name, address, phone, district guess, `create_location` or `update_location` to fill an empty address | Match existing venues by normalised address similarity. No coordinates from the model; apply leaves the row for the existing `rule:missing_coordinates` lookup so grades and district boxes apply. |
| Activities | name and `zh`, description, `category_name`, `age_min`, `age_max` when stated, `create_activity` or `update_activity` | Match existing activities by normalised name. Category resolves exact, alias, normalised; unknown goes to Pending categorisation and is captured, as imports do. |
| Pricing | per activity and venue: `pricing_type`, `amount`, `currency` (HKD default), `sessions_count`, `free_trial_class_offered` | The quote must contain the amount. A venue is resolved when the site has one; otherwise the admin picks it on apply. |
| Schedules | weekly entries with local day and HH:MM in `Asia/Hong_Kong`, `languages` | Only when a day and a time are explicit. Term dates and one-off events are out of scope. |

#### 3. Apply

Apply is synchronous and per proposal: re-check that `current_value`
still matches the stored field (optimistic, as name fixes do), then
write through the existing handler for that entity so validators run,
`catalog_versions` records `reason = 'enrichment'` and
`related_id = run id`, and an audit row `ENRICH_APPLY` lists field
names and ids but no contact values. Applying never changes
`review_status`; Readiness recomputes on its own. Dismiss stores a
hash of the proposed value so a rerun on the same site does not
propose it again. Nothing is auto-applied in the first version, even
at 0.95; deterministic JSON-LD fields are the candidate for an
auto-apply threshold later.

Alternative considered: emit importer JSON and call
`POST /v1/admin/imports` as the sibling does. It gives nested rows and
`import_job_id` on versions, but it matches by `place_id` or manager
plus name, `allow_updates` replaces records rather than fields, and it
adds an import-history job per click. Per-field proposals fit the
pick-and-choose use case. The importer's pricing and schedule
validation functions can still be reused as helpers.

### Data model (red migration)

- `org_enrichment_runs`: `id`, `org_id`, `status`
  (`queued|running|ready|failed|render_required`), `requested_by`,
  `seed_url`, `pages_fetched`, `bytes_fetched`, `duration_ms`,
  `model`, `cost_usd`, `input_hash`, `error`, `processed_message_ids`,
  `created_at`, `finished_at`. Partial unique index on `org_id` where
  status is `queued` or `running`.
- `org_enrichment_proposals`: `id`, `run_id`, `org_id`, `section`,
  `kind` (`update_organization|add_media|create_location|update_location|create_activity|update_activity|create_pricing|create_schedule`),
  `entity_type`, `entity_id` nullable, `field` nullable,
  `current_value` JSONB, `proposed_value` JSONB, `confidence`,
  `unverified` boolean, `evidence` JSONB, `status`
  (`pending|applied|dismissed|superseded`), `proposed_hash`,
  `decided_by`, `decided_at`, timestamps. Index on `(org_id, status)`.
- `org_enrichment_settings`: singleton, fields listed under API.
- `enrichment_fetch_cache`: `url_hash`, `host`, `status`, `kind`
  (`status|robots|backoff`), `expires_at`.

### Infrastructure (red)

- `aws_proxy.py` gains `type: "crawl"` with `fetch_image`; the proxy
  role gains `s3:PutObject` on
  `arn:aws:s3:::<media bucket>/organizations/*/enrichment/*`.
- No new queue. The worker dispatches `enrichment_run_id` before the
  existing keys.
- Environment: `ENRICHMENT_CRAWL_TIME_BUDGET_SECONDS` (60); other
  limits live in the settings row.
- The existing DLQ alarm covers failed runs.

### Files touched if built

- `backend/db/alembic/versions/00xx_org_enrichment.py` (red)
- `backend/src/app/services/aws_proxy.py` (red),
  `backend/infrastructure/lib/api-stack.ts` (red)
- `backend/src/app/services/enrichment/` (crawl plan, parsers, prompt,
  sheet validation, apply), `backend/src/app/api/admin_enrichment.py`,
  `backend/lambda/category_suggestions/handler.py`,
  `backend/src/app/api/admin.py`
- `docs/api/admin.yaml` and generated admin types
- `apps/admin_web/src/components/shared/organizations-panel.tsx`,
  `apps/admin_web/src/components/admin/organization-enrichment.tsx`,
  `apps/admin_web/src/hooks/use-org-enrichment.ts`,
  `apps/admin_web/e2e/organizations.spec.ts` and fixtures
- `docs/architecture/data-quality.md`, `lambdas.md`,
  `aws-messaging.md`, `database-schema.md`

### Phasing

1. Button, run, result card, and Organization plus Media plus
   Locations proposals with apply and dismiss. Deterministic parsers
   and the LLM pass both ship here.
2. Activities, Pricing, and Schedules, which need the venue picker and
   the category resolution path.
3. `render_required` sites through a headless renderer, rerun diffs
   using the normalised page hash as a "site changed" signal, bulk
   enrichment from the Catalog list, and a scheduled refresh.

## Tests

- Backend `pytest`: SSRF guard (private, loopback, CGNAT, redirect to
  private), same-site lock, robots denial, page cap and time budget,
  JSON-LD and OpenGraph parsers on fixture HTML, evidence substring
  check and downgrade, dedupe against existing venues and activities,
  apply guard rails (stale current value, logo requires media URL,
  200 cap), budget refusal, idempotent SQS redelivery, importer group
  refused. Fixtures use fictional providers and no real contact data
  (`scripts/check-pii.sh`).
- `python3 scripts/check_openapi_routes.py` after the YAML change.
- Admin web: vitest for the button states (no website, running,
  historical hidden, manager hidden) and the result card; Playwright
  `e2e/organizations.spec.ts` with a mocked run.
- `npm run lint`, `npm run typecheck`, `pre-commit run ruff-format --all-files`.

## Production signals

None yet. Once built: run count and failure rate per status, pages
per run, cost per run against the monthly limit, DLQ alarm, the
proxy duration p99, and the share of `render_required` sites, which
decides whether phase 3 is worth doing.

## History

- `docs/plans/org-website.md` added `organizations.website`
  (migration `0047`) and made it writable by managers and imports.
- `docs/plans/location-enrichment.md` and `location-enrichment-fixes.md`
  set the lookup-through-proxy pattern, the grades, and the "never
  overwrite a pin" rule this design reuses.
- `docs/plans/org-page-details-header.md` moved the version switcher
  into the Details card title, which is why the button belongs in
  that slot.
- The sibling's `catalog-enrich` duty is the closest working system
  and the source of the crawler rules above.

## Open questions

1. Proxy `type: "crawl"` (Option A) or a dedicated crawler function
   (Option B), given the 500-resource cap.
2. Same-site rule: host with or without `www.` only, or a registrable
   domain rule that needs a public-suffix list.
3. Copy media into the bucket by default, or hotlink. Copying asks for
   a copyright stance in the admin copy, since the images belong to
   the provider.
4. Should applying a new activity on an approved organization enqueue
   a category check, or leave it to the next sweep.
5. Default `monthly_cost_limit_usd`. A run is about eight pages of
   8000 characters, roughly 20k input tokens, which is cents on the
   current `qwen/qwen3-30b-a3b` default; a stronger extraction model
   may be worth a separate setting.
6. Whether the sibling board should call this endpoint instead of
   crawling on its side, so both paths share one crawler and one
   proposal store.
