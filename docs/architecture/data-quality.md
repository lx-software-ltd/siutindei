# Data quality

Admins merge organizations that are the same provider, review display
names that still need the import cleanup rules, and give every
activity a venue. The tools live on the Data quality nav item:
Duplicates, Names, Locations, then Categories.

Endpoint shapes live in `docs/api/admin.yaml` under
`/v1/admin/org-duplicates`, `/v1/admin/name-fixes`, and
`/v1/admin/location-fixes`. A full-access partner API key can read
pending proposals at `GET /v1/partner/name-fixes` and sees
`pending_name_fixes` on `GET /v1/partner/organizations`. The same key
can read venue proposals at `GET /v1/partner/location-fixes`, sees
`pending_location_fixes` on organizations, and sees `location_ids`
plus `pending_location_fix` on activities. It can read category-check
reviews at `GET /v1/partner/category-reviews` and sees
`category_review` on `GET /v1/partner/activities`. A full-access
`crud` key can decide category reviews, decide venue proposals, and
list or delete empty leftover categories. An org-scoped key can read
its own venue rows and receives `403` on those writes. See
`docs/api/partner.yaml`.

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
the merge transaction commits.

`organization_merges` stores the removed `source_id` and `place_id`.
Later imports that look up those values load the survivor. The audit
row uses action `MERGE` and records source ids, moved counts, and
filled field names. Dismissing a pair writes action `DISMISS_DUPLICATE`.

A dry run returns the same plan and writes nothing. Dismissed pairs
are stored on `organization_duplicate_dismissals`. A dismissed pair
is a cannot-link: those two organizations are not placed in the same
group even when a third organization matches both.

Duplicate groups use exact name, phone, email, source id, social, and
website buckets, plus spelling similarity. `pg_trgm` runs when the
dialect is PostgreSQL and the extension exists. A failed similarity
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

Imports apply this to every organization name and append
`Imported name: …` to `source_note` (500 characters). Activity names
are cleaned only when `review_status` is `pending_review`. If the
cleaned name belongs to a different record, the original name is kept
and the import records a warning.

Data quality has four tabs: Duplicates, Names, Locations, and Categories.
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
Apply does not replace a pin that is already stored. Export CSV uses
the current filters. A pin
that falls in a different Hong Kong district, or outside Hong Kong,
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
Gateway cuts the request at 29 seconds; the next sweep continues. A
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
