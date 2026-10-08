# Data quality

Admins merge organizations that are the same provider, and they review
display names that still need the import cleanup rules. Both tools live
on the Data quality nav item: Duplicates, then Names.

Endpoint shapes live in `docs/api/admin.yaml` under
`/v1/admin/org-duplicates` and `/v1/admin/name-fixes`.

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
(`Harbour Club (Central 海港)` becomes `Harbour Club (Central)`). Title
case keeps only configured exception words, and Roman numerals, in
capitals. An empty result keeps the original name.

Imports apply this to every organization name and append
`Imported name: …` to `source_note` (500 characters). Activity names
are cleaned only when `review_status` is `pending_review`. If the
cleaned name belongs to a different record, the original name is kept
and the import records a warning.

Data quality has three tabs: Duplicates, Names, and Category Checks.
Category checks moved here from Categories; `?categoryView=checks`
opens this tab. The Names tab scans stored rows with the same rules and writes
`name_fix_proposals`. The list is cursor paginated. A regular scan
refreshes matching rows and still skips approved organizations'
activities. Sweep scan (`from_scratch`) re-evaluates every name in
the chosen scope (`pending_review` or `all`) and deletes pending
proposals the current rules no longer change. Applying a
proposal updates the record when the stored name still matches the
proposal. A dismissed proposal with the same proposed value is not
created again. The review queue warning `name_needs_cleanup` covers
the organization name, and activity names only while that organization
is `pending_review`. The warning links to this tab.
