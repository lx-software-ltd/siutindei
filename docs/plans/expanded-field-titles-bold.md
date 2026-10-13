# Plan: Bold field titles on expanded records

**Status**: Done
**Zone**: yellow

## Goal

Field titles on an expanded table record use the same bold weight as
Import, History, and File warnings headings (`font-semibold`). Today
`Label` and `AdminReadOnlyValue` render those titles at `font-medium`.

## Non-goals

- Changing table column headers, disclosure titles, or card titles
- Changing Import / History / File warnings section headings
- Changing field values, errors, or layout

## Files

- `apps/admin_web/src/components/ui/label.tsx`
- `apps/admin_web/src/components/ui/admin-read-only-value.tsx`
- `apps/admin_web/tests/components/ui/admin-consistency.test.tsx`
- `.cursor/skills/admin-crud-screen/SKILL.md`
- `docs/architecture/admin-web-ui.md`

Filter fields and login labels share `Label`, so they pick up the same
title weight. That keeps one field-title style.

## Invariants this change preserves

- Field copy, required marks, errors, and grid layout
- Import / History / File warnings heading classes stay `font-semibold`
- Read-only details still use `AdminReadOnlyValue` (`dl` / `dt` / `dd`)

## Done when

- Unit tests assert `Label` and `AdminReadOnlyValue` titles are
  `font-semibold`
- `npm run lint` and `npm run typecheck` in `apps/admin_web`
- Browser check: expand a catalog record and an import-history row;
  field titles match File warnings weight

## Rollback

Revert the branch.

## Open questions

None.
