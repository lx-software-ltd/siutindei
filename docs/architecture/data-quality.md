# Data quality

Admins merge organizations that are the same provider, review display
names that still need the import cleanup rules, give every
activity a venue, and fill missing English, Chinese, and Hong Kong
text. The tools live on the Data quality nav item:
Duplicates, Names, Locations, Translations, then Categories. Release
checks and area readiness live on Catalog.

Endpoint shapes live in `docs/api/admin.yaml` under
`/v1/admin/org-duplicates`, `/v1/admin/name-fixes`,
`/v1/admin/location-fixes`, and `/v1/admin/translation-fixes`. A full-access partner API key can read
pending proposals at `GET /v1/partner/name-fixes` and sees
`pending_name_fixes` on `GET /v1/partner/organizations`. The same key
can read venue proposals at `GET /v1/partner/location-fixes`, sees
`pending_location_fixes` on organizations, and sees `location_ids`
plus `pending_location_fix` on activities. It can read category-check
reviews at `GET /v1/partner/category-reviews` and sees
`category_review` on `GET /v1/partner/activities`. A full-access
`crud` key is the partner equivalent of an admin: it can decide category
reviews, decide venue proposals, set `location_ids` on activity create
and update, merge organizations at
`POST /v1/partner/organization-merges`, approve one organization at
`POST /v1/partner/organizations/{id}/approve` (including `force`),
reject one organization at
`POST /v1/partner/organizations/{id}/reject`, and list or delete empty leftover
categories. An org-scoped key can read
its own venue rows and receives `403` on those writes. See
`docs/api/partner.yaml`.

## Checks by kind

The review queue (`backend/src/app/services/org_review.py`) reads the
listing kind. The rules and their SQL mirrors live in
`org_review_kinds.py`, and a test checks that both flag the same
organizations.

| Issue | `class` | `camp` | `place`, `eat` | `preschool` |
| --- | --- | --- | --- | --- |
| `missing_pricing` | blocker | blocker | not raised | warning |
| `missing_schedule` | blocker | blocker | not raised | not raised |

Warnings, with their thresholds as named constants:

- `catch_all_age`: a class or camp whose ages run from 0 to 18 or more.
  The exact import default, 0 to 18, keeps its own `default_age_range`
  warning instead.
- `hours_as_class_times`: a class with sessions of six hours or more on
  six or more days. Those are opening hours, so the kind is probably
  `place`.
- `class_price_outlier`: a `per_class` or `per_hour` price above
  HK$1,500, which is usually a term fee.
- `verification_stale`: a parent check more than 365 days old, or one
  with no date. It prompts the owner to check again. The public badge
  and the listing stay.
- `camp_without_dates`: a listed camp that has a schedule but no dated
  session ending today or later. Search drops ended sessions, so the
  camp shows as "dates on request" until the next dates are added.

## Area readiness

`GET /v1/admin/org-review/summary?area_id=` adds a `readiness` block
for that area and the areas under it
(`backend/src/app/services/area_readiness.py`). It counts listings per
kind, classes and camps that are complete, and organisers that are
parent-verified. Rejected organisers and listings in hidden categories
are left out. A class is complete with a price, a weekly time, and an
age range that is not a catch-all; a camp needs a price and a dated
session that has not ended. A session that has ended does not count
as a time for either.
The area is ready when at least 80% of its classes and camps are
complete and at least 50% of its organisers are verified
(`READY_COMPLETE_SHARE`, `READY_VERIFIED_SHARE`). Catalog shows the
result in a "Ready to open?" card for the chosen neighbourhood.

To widen `SEARCH_AREA_SCOPE`:

1. On Catalog, choose each area already in the scope and check that it
   still shows Ready.
2. Choose the new area and fix its blockers and warnings until it shows
   Ready.
3. Then the owner adds the area's slug to the `SEARCH_AREA_SCOPE`
   GitHub variable and redeploys.

## Merge

The survivor keeps its name and manager unless the admin picks another
value. Blank contact, place, source, and translation fields are filled
from the organizations being removed. Status and review status stay on
the survivor. Locations, activities, tickets, feedback, API keys, and
category-scan rows move onto the survivor before the source row is
deleted. Locations that share a non-empty address are combined, and
activities that share a name are combined. Different addresses both
stay, even when the places are close. Media URLs are unioned. Object
copy runs only when `ORGANIZATION_MEDIA_BUCKET` and
`ORGANIZATION_MEDIA_BASE_URL` are set and the key is
`organizations/{source id}/…`. The source object is deleted only after
the merge transaction commits. A delete that fails is logged with the
survivor id and the object key. Repeating a completed merge returns
the stored outcome and does not write again. A full-access `crud`
partner key uses `POST /v1/partner/organization-merges` for the same
merge.

`organization_merges` stores the removed `source_id` and `place_id`.
Later imports that look up those values load the survivor. An admin
delete writes a row with `kind` `delete` and no survivor. The row
keeps the place id, catalog source, source id, and names, including
names the organization used before it was renamed, plus the
normalized form of those names. It does not keep email, phone, or
manager id. A later import skips that organization and its children
when the place id matches, when the source id matches the same
catalog, or when a remembered name matches and the file does not
carry a different place id or a different source id for the same
catalog. Names are compared after case-folding and collapsed
whitespace. When catalog version 1 exists, an import that matches
that snapshot is not created again, including after a manager delete.
A manager delete does not write the deletion row, so an organization
with no version 1 can be imported again.

Deleting the survivor converts each merge that pointed at it. Those
rows keep names only, record the person and time of the delete, and
share one deletion group. Forgetting the deleted organization from
Data quality forgets that whole group and marks each organization's
catalog versions `forgotten`. Forgetting one previously merged
identity forgets only that identity. Remember, conversion, and forget
each write an audit row with names and identifiers, not contact
fields. A stored import that skipped the organization as deleted runs
again after the identity is forgotten, including the same uploaded
file. Creating the organization by hand still leaves a live row, and
the next import follows that row. The merge audit
row uses action `MERGE` and records source ids, moved counts, and
filled field names. Dismissing a pair writes action `DISMISS_DUPLICATE`.

A dry run returns the same plan and writes nothing. Dismissed pairs
are stored on `organization_duplicate_dismissals`. A dismissed pair
is a cannot-link: those two organizations are not placed in the same
group even when a third organization matches both.

Duplicate groups use exact name, phone, email, source id, social, and
website buckets, plus spelling similarity. The website bucket matches
the organization's website host and the catalog page host. Shared
social and link hosts, such as facebook.com, instagram.com, and
linktr.ee, are not scored. `pg_trgm`
runs when the dialect is PostgreSQL and the extension exists. A failed similarity
lookup is logged. Otherwise scoring uses `difflib`. A shared location
adds weight only when another signal is already present. The review
queue warning `possible_duplicate` uses the organization name key,
phone, email, or source id, and it skips dismissed pairs. It is not
part of the SQL summary predicates.

## Names

Rules run in a fixed order: HTML entities, Unicode NFKC, whitespace
(including a space before `(` or `[`), trailing punctuation, spacing
between Latin and CJK, known or numeric brackets, title case for
all-caps Latin tokens, then a bilingual split that copies Chinese into
`name_translations.zh` when that key is empty. After that split, brackets
that only held the extracted Chinese are removed (`Harbour Club (海港會)`
becomes `Harbour Club`); brackets that still have English stay
(`Harbour Club (Central 海港)` becomes `Harbour Club (Central)`). A
Chinese-only place or branch tag stays on the English name
(`Fantasy World (深水埗)`, `Super Cube 銅鑼灣店`). A long Chinese venue
prefix with a short English fragment stays mixed
(`荃灣廣場空中樂園 PLAY GARDEN`). Title case keeps configured exception
words, a small built-in set (`SKH`, `HKU`, `YWCA`, and similar), dotted
initialisms (`S.K.H.`, `Y.M.C.A.`), and Roman numerals I–XX in capitals.
Short particles such as in, of, and the are lowercased unless they
start the name or a bracketed phrase. Cantonese romanizations `On`,
`To`, and `Or` stay capitalized. A trailing period on a dotted
initialism is kept (`U.S.A.`). An empty result keeps the original name.

Imports apply this when Names is Apply, and record an applied
proposal instead of appending `Imported name: …`. Older notes are
still read when matching a deleted organization. Propose stores the
raw name and a pending proposal on create. On update it keeps the
stored name and proposes only when that stored name still changes.
Off stores the raw name. Activity names
are cleaned only when `review_status` is `pending_review`. If the
cleaned name belongs to a different record, the original name is kept
and the import records a warning. An import with `allow_updates` false
leaves an existing organization or activity unchanged, including a
name or category already fixed. It still matches an activity whose
stored name is the cleaned form of the name in the file, using the
file's name translations. A skipped activity is not joined to the
imported venue. A new venue on a skipped organization is still created.

An import decides each field the file sends. The base is what the
source last said (`import_baselines`), or version 1 when no baseline
exists yet. A source change on a field nobody edited is written. A
field both sides changed stays as the admin left it and waits in
Import changes. A pending proposal does not change the public
listing. `existing_rows` is `merge` (the default), `apply` (the file
wins for the whole row), or `propose` (every change waits). An
approved organization uses `approved_organizations`, which defaults
to `propose`. A new activity under an approved organization is still
created. `allow_updates` false still skips an existing row and writes
no proposal. It does store the file as the new baseline, so a later
import that allows updates treats that skipped file as what the
source last said. Accept writes one field through the admin update
path. Accept-all requires an organization or an import job. Listing
the queue dismisses a proposal whose record no longer exists.

Imports · Settings stores skip-deleted, name cleanup, the two merge
choices, unknown categories, and whether duplicates, locations, and
categories run after a live import and after a website-enrichment
apply. The row is `import_settings`. PUT replaces every field and
locks the row. A missing row uses merge for existing rows, propose
for approved organizations, and the legacy flag for unknown
categories. Post-import checks use
the queue and skip an unchanged fingerprint. An enrichment apply uses
the duplicates, locations, and categories flags. Duplicates cover that organization. Locations
runs only when the apply saved a venue or an activity. Categories runs
only for activities that apply created. The trigger is `enrichment`.
Names stay on the import write path. A dismiss, a crawl, and an apply
that saves nothing do not queue a run. A failure while staging the run
does not undo proposals that saved. Each apply that still has a check
gets its own run. Model replies are recorded for queued runs, whether
the trigger is import or enrichment, one activity or organization at a
time, and only after the reply parses. A cache hit
is not charged. Manual Location and Category sweeps call the model
directly and stay synchronous. Run again requeues every check, replaces
a failed child scan, and refreshes recorded replies. A busy check stays
queued until the third delivery. The run is then queued again up to
twice, ten minutes apart, so a scan that is still open can finish.
After that the check is marked busy and the remaining checks still run. Reading a run does not write. The Duplicates tab still
scores with `pg_trgm`. A run recomputes with SequenceMatcher only. A
busy or failed check does not fail the import. A pending name proposal
blocks approval.

Data quality tabs are Duplicates, Names, Locations, Translations,
Categories, Runs, and Deleted.
Category checks moved here from the Categories nav item;
`?categoryView=checks` opens this tab. The Status filter defaults to
Pending so the table is the work queue; Any still lists the full
check history. Sweep pending re-evaluates
activities on organizations still in review. Sweep all orgs includes
approved organizations. Auto-assign still applies only while the
organization is `pending_review`. A full-access partner API key can
read confirmed and pending reviews; see
`docs/architecture/category-suggestions.md`.

The Names tab sweeps stored rows with the same rules and writes
`name_fix_proposals`. The list is cursor paginated. Sweep pending
re-evaluates names on organizations still in review. Sweep all orgs
re-evaluates every name and deletes pending proposals the current
rules no longer change. The header checkbox selects the visible
page, then all matching rows. Apply and dismiss send `ids` for
visible rows, or the current filters (including `org_id`) for
all-matching. Applying a
proposal updates the record when the stored name still matches the
proposal. A dismissed proposal with the same proposed value is not
created again. The review queue warning `name_needs_cleanup` covers
the organization name, and activity names only while that organization
is `pending_review`. The warning links to this tab.

## Locations

Activities must be linked to a venue. The Locations tab lists
`location_fix_proposals`. Sweep pending covers organizations still in
review. Sweep all orgs includes approved organizations. An organization
with exactly one location is linked immediately and the proposal is
stored as applied, unless that same venue was dismissed. Pricing or
schedule rows that name one venue stay pending. An activity name
matches a district when it contains one Hong Kong area tag, or the
district's Latin name, ignoring case. An activity whose organization
has no venue is `rule:no_venue`. A name filter matches the
organization and its activities. Anything else is queued for the
model on the category-suggestion queue. The worker reads
`location_scan_run_id` before `scan_run_id`. A dismissed unresolved
row is not queued again. One venue index links that venue. Several
indexes stay unresolved and list every candidate address. The
expanded row links to the Locations screen for that organization.
Proposed addresses are geocoded through the
Nominatim proxy, and again on apply when coordinates are missing or
the address changed. Applying a new location that becomes the
organization's only venue links activities that have no join.
Admin, manager, and partner activity create or update can set
`location_ids` directly, including an organization-scoped key for
its own organization. The response lists those ids in location-id
order. Sending the current list again does not rewrite joins.
Removing a venue that still has pricing or a schedule for that
activity is rejected. A later catalog import does not add a venue
back onto an existing activity; it links a venue only when it
creates the activity. The sweep still skips activities that already
have a join.

The header checkbox selects the visible page, then all matching rows.
Apply selected and Dismiss selected send `ids`, or the current filters
when every matching row is selected. `matched` counts the rows that
call decides, and `truncated` is set when more than 200 match. An
activity row's current label counts that activity's own joins. The
monthly model budget is
`location_fix_settings.monthly_cost_limit_usd` and does not include
category-check spend. The model and fallbacks still come from
category-check settings.

A sweep also checks each location. An empty address stays unresolved.
A location with an address and no coordinates is `update_location`
from `rule:missing_coordinates`. The sweep stores the address and does
not call Nominatim. Look up pins queues those rows on the same
category-suggestion queue with `lookup` set to `nominatim`. Look up
with Google does the same for rows that already have `place_id`, and
stays disabled until `GOOGLE_PLACES_API_KEY` is set. A lookup fresher
than 90 days for the same provider is skipped. A later sweep keeps
that lookup, its pin, and its source. Nominatim waits 2.2
seconds between calls in a batch. Grades are `precise`, `street`,
`coarse`, or `miss`. The pin is stored on the proposal for `precise`
and `street`. Bulk apply writes a `precise` pin that sits in the
location's district. Other grades, and a pin in another district, fail
bulk apply and ask for a single apply. Single apply of a pin outside
the district requires `area_id`. A manual `lat` and `lng` on apply
stores a `manual` grade inside the Hong Kong box. Apply on one row
still looks the pin up when no lookup coordinates are stored, writes
`lat` and `lng` to six decimal places, and leaves `place_id` unchanged.
Apply does not replace a pin that is already stored. A pin that
falls in a different Hong Kong district, or outside Hong Kong,
stays unresolved as `rule:pin_outside_area`. The area chain must
include Hong Kong. District boxes are approximate, match the area
name or a translation, and overlap at a shared boundary so a pin in
both boxes is not flagged. A dismissed location finding matches the
same source. A dismissed pin also matches the rounded coordinates, so
a moved pin is flagged again. A missing Google place id stays an
organization warning and is not a location finding.

A venue-less organization whose `source` is `edb` is matched to the
EDB school register by school number. Name similarity of at least 0.95
creates the venue during the sweep, at most 200 creates per sweep.
Further confident matches are stored as pending `create_location` from
`rule:open_data`. The activity pass still runs. The whole sweep request
stops scanning after 20 seconds and reports `truncated`, because API
Gateway cuts the request at 29 seconds. Organizations, activities, and
locations are scanned least recently scanned first: entities with no
proposal row, then the oldest `updated_at`, then name. The next sweep
therefore continues with the entities the last one did not reach. The
ids with a pending proposal are read once per sweep, so an entity with
nothing to report costs no query. The notice shows how many entities
were scanned. The pending count falls through decisions, Apply
selected, and confident register matches, not through the sweep. A
504 in the Locations tab means the sweep ran but answered late. Similarity from 0.80 up to 0.95 stays pending. A weaker
name is left for the model. A failed register download is not cached
and those organizations are left for the next sweep; the run records
that the register could not be loaded. The register is fetched through
the HTTP proxy. School phone numbers are not stored.

Nominatim queries omit `countrycodes` and append Hong Kong, then drop
hits outside the Hong Kong box, because Nominatim files Hong Kong under
China. The admin address search omits `countrycodes` when Hong Kong is
an active country, for the same reason. A Nominatim or Google transport
failure is not stored as a miss. A stored lookup sets the proposal
source to `lookup:nominatim` or `lookup:google`. Nominatim does not
replace a Google pin or a pin an admin pasted. Google lookups are
capped to what the remaining monthly budget can pay at 0.017 USD each.

When the model names more than one venue, apply can take
`target_location_id` for one listed candidate and creates the same join
as `link_existing`. The proposal kind stays `unresolved`.

`no_locations` stays a blocker. `activity_no_location` is a warning.
`missing_coordinates` stays a blocker until the pin is stored.
All three open this tab.

## Translations

Organization and activity names and descriptions need English, Chinese
(`zh`), and Hong Kong Chinese (`zh-HK`). English is the base column.
Chinese and Hong Kong live in `name_translations` and
`description_translations`. The Translations tab lists
`translation_fix_proposals`. Sweep pending covers organizations still
in review. Sweep all orgs includes approved organizations. A field is
queued when at least one of those three languages has text and another
is missing. A description that is empty in every language is left
alone. The model and fallbacks come from category-check settings.
Spend counts toward `translation_fix_settings.monthly_cost_limit_usd`
and does not include category-check or location-sweep spend. The
worker reads `translation_scan_run_id` before `location_scan_run_id`.
Applying a proposal writes only languages that are still missing. The
source check covers the languages the proposal was made from, so a
language filled by hand later is left as stored. A dismissed proposal
with the same source text is not queued again. The sweep walks
organizations and activities in name order and stops at the entity cap
without loading the rest of the catalog. Created and updated counts are
recorded when the model stores proposals. The scan response reports
cleared, skipped, and queued. The review queue uses the same gap: a
warning for each missing required language when some text exists. A
blank description is not a translation warning.
