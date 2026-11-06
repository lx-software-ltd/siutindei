# Plan: Close leaflet enrichment review findings

**Status**: Done
**Zone**: yellow, plus red for the media bucket policy and the Lambda
bundle command. Both are the fixes named in the review.

## Goal

A leaflet run spends vision money only inside the monthly budget, fails
clearly when a picture has no vision slot, and does not treat a
transcript as a fetched page. Pending files are size-capped, tagged,
deleted when unused, and unreadable without a signature on a bucket
this stack creates. The Docker bundle installs the same wheel tags as
the local bundle.

## Non-goals

- A lifecycle rule on a media bucket this stack imports by name. That
  bucket is not a resource of this stack.
- Rendering PDF pages that Pillow and a raw JPEG stream cannot decode.

## Files

- `backend/src/app/services/enrichment/leaflet.py`
- `backend/src/app/services/enrichment/leaflet_objects.py`
- `backend/src/app/services/enrichment/leaflet_vision.py`
- `backend/src/app/services/enrichment/leaflet_stage.py`
- `backend/src/app/services/enrichment/run.py`
- `backend/src/app/services/enrichment/apply_media.py`
- `backend/src/app/services/enrichment/apply.py`
- `backend/src/app/services/enrichment/pdf.py`
- `backend/src/app/services/enrichment/proxy_crawl.py`
- `backend/src/app/services/enrichment/store.py`
- `backend/src/app/services/enrichment/extract.py`
- `backend/src/app/services/enrichment/sheet.py`
- `backend/src/app/services/enrichment/parse.py`
- `backend/src/app/api/admin_enrichment.py`
- `backend/infrastructure/lib/api-stack.ts`
- `backend/infrastructure/lib/constructs/python-lambda.ts`
- Admin leaflet dialog, OpenAPI, architecture docs, tests

## Invariants this change preserves

- Catalog `media_urls` change only when a proposal is applied.
- A picture proposal stays a caller-supplied file. PDF rasters stay
  under `rasters/` and are not valid upload keys.
- Public URL fetches stay on the proxy, with `check_fetch_url` on
  every hop.
- The importer group still cannot presign, apply, or dismiss.

## Done when

- Leaflet, partner, importer, and bundle pytest modules pass.
- `ruff check` on the edited Python passes.
- Admin lint, typecheck, the enrichment vitest, and the organizations
  Playwright spec pass.
- `npm run build` in `backend/infrastructure` passes.

## Rollback

Revert the branch. Pending objects already tagged expire only where the
bucket lifecycle rule was deployed. Applied media keys are untagged.

## Open questions

None.
