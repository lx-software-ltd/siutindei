# Plan: Website enrichment media preview

**Status**: Done
**Zone**: yellow

## Goal

In the website enrichment card, a Media proposal shows the image itself. The source URL is no longer printed in the proposal value.

## Non-goals

No change to crawl, copy, or apply. `source_url` stays the value that apply reads. Other proposal kinds stay text. The Media tab grid is unchanged.

## Files

- `apps/admin_web/src/components/admin/organization-enrichment-proposals.tsx` — render an image for `add_media`
- `apps/admin_web/tests/components/admin/organization-enrichment-proposals.test.tsx` — preview, hidden URL, unsafe URL
- `apps/admin_web/e2e/fixtures/test-fixtures.ts` — one media proposal and a stub image
- `apps/admin_web/e2e/organizations.spec.ts` — the enrichment spec expects the preview

## Invariants this change preserves

- Apply still copies from `source_url`.
- Only `http` and `https` URLs are requested as images.
- A description or other non-media proposal still renders as text.
- The copyright notice on the card stays.

## Done when

`npm test -- tests/components/admin/organization-enrichment-proposals.test.tsx`, `npm run lint`, and `npm run typecheck` pass in `apps/admin_web`. The organizations Playwright spec shows the media preview and does not show the source URL.

## Rollback

Revert the commit. Proposals go back to printing `source_url`.

## Open questions

None.
