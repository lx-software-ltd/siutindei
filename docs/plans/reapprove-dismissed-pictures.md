# Plan: Re-approve dismissed pictures, and fit website photos to the tile

**Status**: Done
**Zone**: yellow

## Decisions

1. Re-approval is only for picture rows (`kind` `add_media`, including a
   logo). A dismissed description, venue, activity, price, or schedule
   stays final. Applying one of those again can create a second
   catalog row.
2. Apply uses the existing media path. A dismissed picture becomes
   `applied` and is copied or attached the same way as a pending one.
   Every other dismissed row with that hash becomes `superseded`, so
   the hash leaves the dismissed set even when two runs stored it.
3. The enrichment card lists website pictures dismissed on an earlier
   website run when the run being read no longer has that hash. One
   row per hash, the newest decision, at most the media-list cap.
   Reading an older run does not pull a picture dismissed later. A
   leaflet run is not mixed with a website run. The returned list is
   ordered in one place, so merging rows does not reshuffle the run.
4. Dismiss still accepts only `pending` rows. The apply bar stays up
   while any row is pending. When the only selectable rows are
   dismissed pictures, the bar appears once one of them is selected.
   An unsaved Details form shows the save-or-discard note whenever
   that bar is up. A failed re-apply shows its reason on the row.
5. A dismissed leaflet cannot be selected and apply refuses it. Its
   file was deleted on dismiss. Website pictures are copied from
   `source_url` at apply time, so they do not need a stored object.
6. Public photos fill their tile. The frame has a definite size and
   hides overflow. The image is taken out of flow and painted with
   `object-cover`. Logos stay `object-contain` and are also taken out
   of flow so a wide mark cannot stretch the tile. From tablet width
   up, the gallery mosaic is two rows and the main photo spans both.
   Lightbox photos sit in equal frames and show the whole picture.
7. An apply that mixes runs still links the catalog version. The
   linked run is the newest applied proposal's run.

## Goal

On the organization website-enrichment card, an admin can select
picture rows that were dismissed and apply them. Those pictures stay
reachable after a later crawl, which today drops a dismissed hash and
shows only the latest run.

On the public website, a listing card, map thumbnail, and activity
gallery tile keeps its shape. The photo covers that tile. A tall or
wide source does not stretch the tile or spill into the next cell.

## Non-goals

- A new route, a schema change, or a seed change. Apply and dismiss
  stay the same paths. `backend/db/**` and `backend/infrastructure/**`
  stay untouched.
- Re-opening dismissed non-picture proposals.
- Changing which photo is chosen, or picking a focal point other than
  the center.
- Keeping a dismissed leaflet file after dismiss. The delete-on-dismiss
  behavior stays.
- The admin media grid and the enrichment preview. The preview already
  sits in a fixed box with `object-contain`.
- Stopping a later crawl from suggesting a source again after the
  picture has been applied. That matches pictures applied the first
  time: the stored URL is the copy, not `source_url`.

## What is true today

The card returns proposals for the latest run only. A checkbox is
enabled only when `status` is `pending`. Apply refuses anything else
with `not pending`. Dismiss writes `dismissed` and stores
`proposed_hash`. The next crawl skips that hash, so the picture never
comes back as a pending row. If the latest run is a newer crawl, the
old dismissed row is not on the card at all.

Public listing and gallery photos already say `object-cover`, but the
image is still in normal flow. Gallery mosaic cells take their
minimum size from the picture, then the outer frame clips them. The
lightbox uses `object-cover` with no height, so a tall photo is not
held inside the dialog.

## Files

- `backend/src/app/services/enrichment/apply.py` — accept a dismissed
  website picture. A dismissed leaflet stays refused. Applying a
  picture supersedes the other dismissed copies of its hash. A mixed
  apply still links the catalog version to the newest run.
- `backend/src/app/api/admin_enrichment.py` — merge earlier website
  pictures into a website run, one per hash, capped, and sort every
  read the same way.
- `docs/api/admin.yaml` — one sentence on apply: a dismissed picture
  can be applied later. The dismiss sentence stays: a hash that is
  still dismissed is not suggested again.
- `docs/architecture/database-schema.md` — the hash sentence notes
  that applying the picture clears that block.
- `apps/admin_web/src/components/admin/organization-enrichment.tsx`
  and `organization-enrichment-proposals.tsx` — a row is selectable
  when it is pending, or dismissed and `add_media`. Apply shows when
  any selectable row exists. Dismiss stays disabled unless the
  selection contains a pending row, and the request sends only those
  pending ids. Logo selection still keeps a single logo, including a
  dismissed one.
- `apps/admin_web/e2e/organizations.spec.ts` and the enrichment fixture
  — one dismissed picture can be selected and applied. A dismissed
  non-picture stays unchecked and disabled.
- `apps/public_www/src/components/sections/listings/listing-card.tsx`
- `apps/public_www/src/components/sections/search/search-map-list-item.tsx`
- `apps/public_www/src/components/sections/activity-detail/activity-gallery.tsx`
  — shared tile classes: frame `relative overflow-hidden`, photo
  `absolute inset-0 h-full w-full object-cover`, logo
  `absolute inset-0 h-full w-full object-contain`. Mosaic buttons get
  `h-full min-h-0`. The lightbox image is `max-h-[70vh] w-full
  object-contain`.
- Component tests next to those files.

## Invariants this change preserves

- Nothing is written until apply. A dismissed hash that is still
  dismissed is not proposed again.
- Apply and dismiss stay admin-only on the admin API, and full-access
  `crud` on the partner API, because both call the same functions.
- One logo per apply. Media still goes through `apply_media`.
- A failed picture does not undo other ids in the same request.
- Contact values stay out of logs. The copyright notice stays off the
  public site.
- Pending categorisation, crawl limits, and the importer group are
  unchanged.

## Done when

- `pytest tests/test_org_enrichment.py tests/test_partner_org_enrichment.py`
  covers: apply of a dismissed picture succeeds and sets `applied`;
  apply of a dismissed non-picture is `not pending`; a later save
  still skips a hash that remains dismissed; GET includes one older
  dismissed picture and omits an older dismissed description; GET
  does not duplicate a hash already on the latest run.
- `npm run lint` and `npm run typecheck` in `apps/admin_web`, plus the
  enrichment component tests. Playwright
  `e2e/organizations.spec.ts` selects a dismissed picture and posts
  it to apply.
- `npm run lint`, `npm run typecheck`, and `npm test` in
  `apps/public_www`. Listing, map, and gallery tests assert the tile
  classes above.
- Browser check of the public listing card, the activity gallery
  mosaic, and the lightbox, at a desktop width and a phone width,
  with a portrait photo and a wide photo.
- `pre-commit run ruff-format --all-files` before the Python commit.
- No seed change. No OpenAPI route added, so the route and lambda
  catalog checks are unchanged.

## Rollback

Revert the commit. Stored rows stay as they are. Pictures already
re-applied remain on the organization. Dismissed hashes that were not
applied keep blocking the next crawl.

## Open questions

None. Re-approval is pictures only, and public tiles crop to the frame
rather than letterboxing the photo.
