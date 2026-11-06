# Research: Enrichment "Now: Empty" and template description warning

**Status**: Implemented from `docs/plans/enrichment-now-empty-and-template-flag.md`
**Zone**: yellow

Partner GET on 6 Nov 2026 (Hong Kong time) for The International
Montessori School. Counts and field presence only; no contact or
address values.

## Entry points

- Admin Website enrichment card:
  `apps/admin_web/src/components/admin/organization-enrichment.tsx`
  loads `GET /v1/admin/organizations/{id}/enrichment`. Partner is the
  same payload from `GET /v1/partner/organizations/{id}/enrichment`
  (`backend/src/app/api/partner_org_enrichment.py`).
- "Now" text:
  `apps/admin_web/src/components/admin/organization-enrichment-proposals.tsx`
  `proposedText(row.current_value)`. `null` becomes the word `Empty`.
- Apply conflict check uses the **stored** snapshot, not the GET
  payload: `backend/src/app/services/enrichment/apply_rows.py`
  `_still` / `_empty_translation`.
- Readiness warning:
  `backend/src/app/services/org_review.py` `collect_issues` emits
  `source_attribution` / "Description is a template" when
  `organization.description_source == "template"`. SQL twin:
  `backend/src/app/services/org_review_sql.py` `_issue_predicates`.
- Public search blanks org and activity descriptions when
  `description_source == "template"`:
  `backend/src/app/api/search.py`. Category recheck also treats
  `template` or unset as untrusted:
  `backend/src/app/services/category_suggestions/prompt.py`
  `_description_is_untrusted`.

## Owners

Admin console, enrichment, and org review.

## Callers

Admin Details (Website enrichment + Readiness). Full-access `crud`
partner keys read the same enrichment payload. Search and category
recheck read `description_source`.

## Existing abstractions

- Extract writes `current` from the org snapshot
  (`backend/src/app/services/enrichment/extract.py` `_current_for`).
  Empty strings become `None`.
- `prepare_proposals` then replaces org-field currents with
  `_live_current` (`backend/src/app/services/enrichment/match.py`),
  which copies `getattr(org, key)` including SQL `NULL`. Result:
  `{ "email": null }` rather than JSON `null`.
- `add_media`, `create_location`, `create_activity`, `create_pricing`,
  and `create_schedule` always store `current: None`
  (`extract.py` `_record`, `logos.py`).
- GET `_read` in `backend/src/app/api/admin_enrichment.py` serializes
  the stored JSON. It does not refresh from the live organization.
- Apply of `description` writes `org.description` only
  (`apply_rows.py` `_apply_org`). It does not set
  `description_source` to `enrich`. Admin PUT sends whatever the
  Description origin dropdown still holds
  (`apps/admin_web/src/components/shared/organizations-panel.tsx`).

## Tests

- Enrichment apply: `tests/test_org_enrichment.py` (description apply
  does not assert `description_source`).
- Proposal "Now: Empty":
  `apps/admin_web/tests/components/admin/organization-enrichment-proposals.test.tsx`
  expects that label when `current_value` is `null`.
- Review issues: `tests/test_org_review.py` has no
  `source_attribution` / template-description case.
- Public listing: `apps/public_www/tests/lib/listing-utils-status.test.ts`
  `isTemplateDescription` is the `descriptionSource === 'template'`
  flag, not the text.

## Production signals

Partner list `q=International Montessori School` returned one
organization, pending review, source `edb`.

- English `description` is unique website copy (length 299), applied
  from the latest enrichment run. The crawl snapshot on those
  description proposals is the older EDB sentence ("…class or
  early-years centre in SOUTHERN…").
- `description_source` is still `template`.
- Chinese `description_translations.zh` is still the generic district
  boilerplate (mentions SOUTHERN).
- Logo URL is set. `media_urls` has 4 entries. Four venues exist.
- Latest enrichment run `ready`, 12 pages, 128 proposals (117
  dismissed, 11 applied). No pending rows.
- 110 / 128 proposals have `current_value` JSON `null` (every
  `add_media`, `create_location`, `create_activity`,
  `create_schedule`). The UI prints `Now: Empty` on each of those
  rows, including Logo while a logo is saved, and photos while four
  images are saved.
- Org-field rows that were blank at crawl time are `{ "email": null }`
  (and the same shape for Facebook / Instagram). `proposedText` prints
  `email: ` with nothing after the colon. GET does not replace this
  with the live values that apply already wrote.

## History

EDB import tagged the original boilerplate as `descriptionSource=template`
(`backend/src/app/api/admin_imports_catalog.py`). Enrichment later
replaced the English text and did not retag the column. Search still
treats the live English copy as a template.

## Open questions

Answered for the plan: GET "Now" should be the live catalog; apply
keeps the stored snapshot. Applying a description sets
`description_source` to `enrich`. Existing stale rows need a
non-migration way to clear the warning (heuristic and/or the origin
dropdown). Leftover Chinese boilerplate after an English apply is a
follow-up, not this warning's root cause.
