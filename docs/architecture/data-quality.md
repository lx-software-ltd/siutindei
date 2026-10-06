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
deleted. Media URLs are unioned. Object copy runs only when
`ORGANIZATION_MEDIA_BUCKET` and `ORGANIZATION_MEDIA_BASE_URL` are set
and the key is `organizations/{source id}/…`.

`organization_merges` stores the removed `source_id` and `place_id`.
Later imports that look up those values load the survivor. The audit
row uses action `MERGE` and records source ids, moved counts, and
filled field names.

A dry run returns the same plan and writes nothing. Dismissed pairs
are stored on `organization_duplicate_dismissals` and are not grouped
again.

Duplicate groups use exact name, phone, email, source id, social, and
website buckets, plus spelling similarity. `pg_trgm` runs when the
dialect is PostgreSQL and the extension exists. Otherwise scoring uses
`difflib`. A shared location adds weight only when another signal is
already present. The review queue warning `possible_duplicate` uses
exact name, phone, email, or source id only.

## Names

Rules run in a fixed order: HTML entities, Unicode NFKC, whitespace,
trailing punctuation, spacing between Latin and CJK, known or numeric
brackets, title case for all-caps Latin tokens, then a bilingual split
that copies Chinese into `name_translations.zh` when that key is empty.
An empty result keeps the original name.

Imports apply this to every organization name and append
`Imported name: …` to `source_note` (500 characters). Activity names
are cleaned only when `review_status` is `pending_review`. If the
cleaned name belongs to a different record, the original name is kept
and the import records a warning.

The Names tab scans stored rows with the same rules and writes
`name_fix_proposals`. Applying a proposal updates the record. A
dismissed proposal with the same proposed value is not created again.
The review queue warning `name_needs_cleanup` links to this tab.
