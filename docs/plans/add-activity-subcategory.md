# Plan: Add an activity subcategory from the dropdown

**Status**: Done
**Zone**: yellow

## Goal

On an activity subcategory dropdown, offer “— Add a new subcategory —”. Choosing it reveals a name field that creates a child of the category selected for that activity. The new subcategory is selected for this activity and appears at once in every other subcategory dropdown that shares that parent.

## Non-goals

- Adding a root category from the Category dropdown.
- Letting a manager create catalog categories.
- A database migration or a change to the category create API.
- Saving the activity itself when the subcategory is created.

## Files

- `apps/admin_web/src/lib/activity-category-tree.ts` — insert a child and notify mounted category trees.
- `apps/admin_web/src/hooks/use-activity-categories.ts` — apply those inserts to the loaded tree.
- `apps/admin_web/src/components/ui/cascading-category-select.tsx` — the option, the name field, and the create request.
- `apps/admin_web/src/components/shared/activities-panel.tsx` — admins only.
- `apps/admin_web/tests/components/ui/cascading-category-select.test.tsx`
- `apps/admin_web/e2e/activities.spec.ts`

## Invariants this change preserves

- Choosing an existing subcategory still sets that category id.
- The sentinel value is never stored as an activity category.
- A category with no children still hides the subcategory dropdown for managers.
- Pending categorisation cannot be a parent.
- Creating the subcategory uses the existing admin create route and does not change the activity until the activity editor is saved.

## Done when

- `npm run test -- tests/components/ui/cascading-category-select.test.tsx` in `apps/admin_web`.
- `npm run lint` and `npm run typecheck` in `apps/admin_web`.
- Playwright `e2e/activities.spec.ts` covers adding a subcategory and selecting it on another activity.

## Rollback

Revert the commit. Categories created while the feature was deployed remain in the catalog.

## Open questions

None. A new subcategory is a child of the category selected on that dropdown, so another activity sees it when that activity’s subcategory list uses the same parent.
