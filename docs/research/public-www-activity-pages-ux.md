# Research: How the public website shows activity information

**Status**: Draft
**Zone**: this memo is green. The follow-up work is green
(`apps/public_www/**`) with one yellow slice (search API and
`docs/api/search.yaml`). The plan is
`docs/plans/public-www-activity-pages-ux.md`.

## Summary

The activity detail page shows about a third of what the search API
already returns for it, in one unlabelled column of text, and three of
the facts it does show are wrong or misleading. Branding was out of
scope. This memo covers how information is shown on the activity
detail page, the listing card, the search list, and the search map at
six viewports.

The three findings to fix before any redesign:

1. Class times are printed in UTC. A Monday 10:00 class in Hong Kong
   shows as "Mon 02:00".
2. On the English site, an activity or organisation that has a `zh`
   translation shows its Chinese name.
3. An activity with two venues or two prices shows as two identical
   cards, and its detail page shows only the first venue and price.

## Method

Rendered `apps/public_www` in dev mode on 11 Nov 2026 with
`NEXT_PUBLIC_STAGING_SEARCH_DATA_ENABLED=true`, driven by Playwright
with system Chrome. The staging fixture's image host no longer answers
and every fixture record is equally complete, so the run swapped in a
rewritten fixture: full records (five photos, two-paragraph
description in both languages, three weekly sessions, term price with
a session count, free trial, two languages, place id), typical
records, and sparse records (no price or schedule, no photo, logo
only, template description, temporarily closed). All names are
fictional. The map view was rendered with a placeholder key and a
stubbed Maps script, so map tiles in the evidence are not real.

| Viewport | CSS px |
| --- | --- |
| Mobile portrait | 390 x 844 |
| Mobile landscape | 844 x 390 |
| iPad portrait | 820 x 1180 |
| iPad landscape | 1180 x 820 |
| PC landscape | 1440 x 900 |
| PC portrait | 1080 x 1920 |

Not measured: real production data, real Google map tiles, Safari, and
the Flutter app.

## Entry points

- Detail route: `apps/public_www/src/app/[locale]/activity/page.tsx`
  renders `src/components/pages/activity-detail-route.tsx`, which reads
  `?id=` and mounts `src/components/pages/activity-detail-page.tsx`.
- Listing card: `src/components/sections/listings/listing-card.tsx`,
  laid out by `listing-grid.tsx` (search list) and
  `listing-carousel-section.tsx` (home).
- Search: `src/components/pages/search-results-page.tsx`, with
  `src/components/sections/search/search-map-split-layout.tsx`,
  `search-map-list-item.tsx`, `search-view-toggle.tsx`, and
  `filter-chip-row.tsx`.
- Formatting: `src/lib/activities/listing-utils.ts`.
- Wire mapping: `src/lib/activities/map-listing.ts` into the model in
  `src/lib/activities/types.ts`.
- Backend: `backend/src/app/api/search.py`,
  `backend/src/app/api/search_page.py` (`map_row_to_result`),
  `backend/src/app/api/schemas.py`, and `build_search_query` in
  `backend/src/app/db/queries.py`.

## Owners

Public website and search API owners. No red path is needed for the
recommended work: CloudFront forwards every query string
(`backend/infrastructure/lib/public-www-stack.ts`), so a new search
parameter needs no infrastructure change.

## Callers

`GET /v1/activities/search` is also called by the Flutter app
(`apps/siutindei_app`) and by partners. Any response change must be
additive.

## Findings: activity detail page

### What a parent sees first

Measured on the fullest record. "CTA" is the "Ask on WhatsApp" button.

| Viewport | Layout | Photo | Title starts at | CTA starts at | Result |
| --- | --- | --- | --- | --- | --- |
| Mobile portrait | 1 column | 358 x 269 | 493 px | 1081 px | CTA is 237 px below the first screen |
| Mobile landscape | 1 column | 796 x 597 | 776 px | 1144 px | First screen is the header and part of a photo. The photo is taller than the screen |
| iPad portrait | 1 column | 772 x 579 | 758 px | 1154 px | Photo fills half the screen. CTA sits on the fold |
| iPad landscape | 2 columns | 528 x 396 | 147 px | 599 px | Fits. Page ends at 675 px, then 232 px of blank |
| PC landscape | 2 columns | 528 x 396 | 147 px | 599 px | Fits. 312 px of blank before the footer |
| PC portrait | 2 columns | 492 x 369 | 147 px | 599 px | Content uses the top 675 px of 1920. About 1330 px of blank |

The two-column layout starts at `lg` (1024 px), so iPad portrait and
mobile landscape get the phone layout with a larger photo. The blank
space on desktop comes from `main` being `min-h-screen`
(`src/components/shared/page-layout.tsx`) around a short article.

### Information shown against information available

| Fact | In the `full` API response | Shown today |
| --- | --- | --- |
| Activity name | yes | yes |
| Organisation name | yes | yes, small uppercase line |
| Price | yes | yes, without the session count: "HK$2,400 / term" |
| Sessions in a term | `pricing.sessions_count` | no |
| Free trial | yes | yes, as a plain list line |
| Region | yes | yes |
| Neighbourhood | `location.area_id`, labels in `src/data/home_wizard_choices.json` | no |
| Address | yes | yes |
| Coordinates | `location.lat`, `location.lng` | no map, no directions link without a place id |
| Weekly sessions | all entries, with end times | first entry only, start time only, in UTC |
| Teaching languages | `schedule.languages` | no |
| Age range | `activity.age_min`, `activity.age_max` | no |
| Category | `activity.category_id`, labels and icons in the website | no |
| Photos | all `organization.media_urls` | first photo only |
| Logo | `organization.logo_media_url` | only as a stretched stand-in when there is no photo |
| Activity description | yes | yes, paragraph breaks collapsed |
| Organisation description | yes, with translations | no. `map-listing.ts` drops the translations |
| Temporarily closed | yes | yes |

Held in the database but not in the search response (model files
under `backend/src/app/db/models/`, summary in
`docs/architecture/database-schema.md`):

| Fact | Where | Needs |
| --- | --- | --- |
| Venue name | `locations.name` | additive field |
| Other venues, times, and prices of the same activity | one search row each | detail lookup returns all rows |
| Other activities by the organisation | `activities.org_id` | a filter parameter |
| Organisation website and social links | `organizations.website`, `instagram`, `facebook`, and others | product decision first |
| Parent feedback | `organization_feedback` stars, labels, text | product decision first |
| Last updated | `organizations.updated_at` | additive field |

### Structure and reading order

- One `h1` and no section headings. Facts are an unlabelled list of
  four text lines with no icons, so "Hong Kong Island", an address,
  "Mon 02:00", and "Free trial available" read as one paragraph.
- The description is one `<p>` with default white-space. A
  two-paragraph description renders as one block.
- No way back to the results, no breadcrumb, no share, and nothing to
  look at next: no other activities from the organisation and no
  similar activities nearby.
- The primary action is at the end of the text. On phones the floating
  "Chat on WhatsApp" button (`src/components/shared/whatsapp-fab.tsx`)
  sits on top of the description and on top of the in-page "Ask on
  WhatsApp" button. The floating one opens a chat with no activity
  context. The in-page one names the activity.
- "Open in Google Maps" appears only when the organisation has a place
  id, even when the venue has coordinates.

### Sparse, loading, and error states

- No price and no schedule prints "Price on request" and "Schedule to
  be confirmed" in the same slots as real values, so a sparse record
  reads as a broken one.
- A template description prints "Details coming soon".
- No photo prints "Photo coming soon" on a large yellow block. A logo
  is stretched and cropped into the 4:3 photo slot.
- A photo URL that fails shows the browser's broken-image icon and the
  alt text. There is no `onError` fallback.
- Loading is one line of text. In the measured phone case the content
  area grew from 152 px to 884 px when the data arrived, so the page
  jumps.
- "Activity not found." and the load error are one red line with no
  link to search or home.

### Accuracy

- **UTC times.** `formatScheduleSnippet` in `listing-utils.ts` prints
  `dayOfWeekUtc` and `startMinutesUtc` as stored. The importer stores
  UTC (`backend/src/app/api/admin_imports_utils.py`) and the admin
  console converts back (`apps/admin_web/src/lib/schedule-form-utils.ts`).
  The website does not. Every time on a card, map row, and detail page
  is eight hours early, and a class before 08:00 Hong Kong time shows
  the previous day.
- **Chinese names on the English site.** `pickTranslation` returns
  `translations.zh` before `translations.en` for every locale. The
  importer writes the `zh` key
  (`backend/src/app/api/admin_imports_catalog.py`). Reproduced: a
  record with `{en, zh}` renders its `zh` name as the `h1` on `/en/`.
  No test covers `pickTranslation`.
- **One activity, several rows.** Search returns one row per activity,
  venue, and price. `use-activity-search.ts` does not group them and
  `listing-grid.tsx` keys by activity id, so a two-venue activity
  renders two identical cards with a duplicate-key warning.
  `fetchActivityListingById` asks for `limit: 1`, so the second venue
  and its price never appear.
- **Hidden default filter.** `DEFAULT_SEARCH_FILTERS.ageGroupId` in
  `src/lib/activities/search-params.ts` is "3-6 years". Results are
  filtered by an age that no card displays.

## Findings: listing card and search list

| Viewport | Cards per row | Card size | Note |
| --- | --- | --- | --- |
| Mobile portrait | 1 | 358 x 367 | About 1.5 cards per screen, 30 per page |
| Mobile landscape | 2 | 382 x 408 | Header and chip row use 182 of 390 px. No whole card fits |
| iPad portrait | 2 | 370 x 399 | Same card size as a phone on a screen twice as wide |
| iPad landscape | 3 | 351 x 384 | Works |
| PC landscape | 4 | 280 x 331 | Works |
| PC portrait | 3 | 317 x 359 | Works |

- Every card carries the same "Parent-Verified" badge. It is hardcoded
  in `listing-card.tsx`, so it does not separate one card from another.
- The meta line is `organisation · region · schedule` in one run of
  text. It wraps to two or three lines and repeats "Schedule to be
  confirmed" down the page.
- Cards show no age range, neighbourhood, or category, the three
  things a parent filters by.
- A card has three links to the same page (image, title, price) and a
  region link in the middle of the text.
- No result count, no sort, and no summary of active filters. The API
  supports price, pricing type, single day, time, and language filters
  (`docs/api/search.yaml`). The website sends age, area, category, and
  text only. The API has no free-trial filter, no total count, and no
  sort: rows come back ordered by session day and time in UTC.
- Filter chips are 38 px tall and the carousel "See all" control is
  32 x 32, both under the 44 px touch guideline. Carousels have no
  arrows on pointer devices.
- The mini map covers the bottom 38% of the photo on the first six
  cards only.
- Loading skeletons use the carousel width (`w-[280px]`) inside the
  grid.

## Findings: search map

Map is the default search view when a Maps key is configured.

- **Mobile portrait.** The map shows one summary card for the selected
  pin. There is no way to browse results without tapping pins. The
  card is overlapped by the WhatsApp button and the list toggle.
- **Mobile landscape.** The map is about 230 px tall and the summary
  card covers most of it.
- **iPad portrait.** Same as the phone layout with a stretched card.
  The split view starts at `lg`.
- **iPad landscape, PC.** A 50/50 split. Rows show a thumbnail, title,
  region, and price. Clicking a row selects its pin, and a small arrow
  is the only way to open the activity. The list toggle floats over
  the last row. "Load more" sits under the split, outside the
  scrolling list.
- **Enlarged map.** The summary card stretches to about 1000 px wide
  and covers the zoom controls.
- **Pins.** 36 px category icons with no background, no price, and no
  clustering. The selected pin only grows to 48 px.

## Existing abstractions

- Category and region icons: `src/lib/home-wizard/choice-icons.ts` and
  `public/images/categories/*.svg`.
- Area labels in both languages:
  `src/data/home_wizard_choices.json` (regions and 123 neighbourhoods).
- Carousel: `src/components/shared/ui/carousel.tsx` and
  `listing-carousel-section.tsx`.
- Modal: `src/components/shared/ui/modal.tsx`, tested in
  `tests/components/modal.test.tsx`.
- Skeleton: `src/components/shared/ui/skeleton.tsx`.
- Maps: `src/components/shared/maps/activity-google-map.tsx` and the
  static-map helper behind `listing-card-mini-map.tsx`.
- Tracked WhatsApp link: `src/components/shared/tracked-whatsapp-link.tsx`.
- Copy: `src/content/en.json`, `src/content/zh-HK.json`, and
  `src/content/types.ts`.

## Tests

- `apps/public_www/tests/components/activity-detail-page.test.tsx`
  covers analytics only. Nothing asserts what the page shows.
- `tests/lib/listing-utils-status.test.ts` covers status helpers. No
  test covers `pickTranslation`, `formatScheduleSnippet`, or
  `formatListingPrice`.
- `tests/components/search-results-page.test.tsx`,
  `search-map-split-layout.test.tsx`, and
  `listing-carousel-section.test.tsx` cover search and cards.
- `apps/public_www/e2e/smoke.spec.ts` is the Playwright smoke run.
  `e2e/footer-layout.spec.ts` is the pattern for viewport assertions.

## Production signals

None read for this memo. The detail page fires `view_item` and the
WhatsApp link fires `generate_lead` with lead type `whatsapp_activity`
(`src/lib/analytics/data-layer.ts`), so the share of detail views that
reach WhatsApp is measurable before and after.

## History

- `docs/plans/search-incomplete-approved.md` added activities with no
  price or schedule to search, which is why the sparse states matter.
- `docs/plans/hk-neighbourhoods.md` added the neighbourhood labels the
  detail page can reuse.

## Open questions

1. Should organisation contact details, website, and social links be
   public, or do all enquiries go through the site WhatsApp?
2. Is approved parent feedback meant to be public?
3. What backs "Parent-Verified"? If nothing per listing, it should not
   be a per-card badge.
4. Do production records carry `zh`, `zh-HK`, or both? That decides
   the fallback order in `pickTranslation`.
