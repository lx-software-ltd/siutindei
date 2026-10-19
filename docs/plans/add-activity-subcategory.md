# Plan: Add an activity subcategory from the dropdown

**Status**: Done
**Zone**: yellow

## Goal

On an activity subcategory dropdown, offer “— Add a new subcategory —”. Choosing it reveals a name field that creates a child of the category selected for that activity. The new subcategory is selected for this activity and appears at once in every other subcategory dropdown that shares that parent.

## Non-goals

- Adding a root category from the Category dropdown.
- Letting a manager create catalog categories.
- Showing the add option on enrichment rows or the category-suggestion dialog. The prop defaults off and only the activity editor turns it on for admins.
- A database migration. Exact duplicates are already rejected by `uq_activity_category_parent_name`. Create and update also reject a sibling whose name differs only by case.
- Saving the activity itself when the subcategory is created.

## Files

- `apps/admin_web/src/lib/activity-category-tree.ts` — insert a child and notify mounted category trees.
- `apps/admin_web/src/hooks/use-activity-categories.ts` — apply those inserts to the loaded tree.
- `apps/admin_web/src/components/ui/cascading-category-select.tsx` — the option, the name field, and the create request.
- `apps/admin_web/src/components/shared/activities-panel.tsx` — admins only.
- `apps/admin_web/tests/components/ui/cascading-category-select.test.tsx`
- `apps/admin_web/e2e/activities.spec.ts`
- `backend/src/app/services/activity_categories.py` — reject a sibling name that differs only by case.
- `tests/test_activity_category_names.py`

## Invariants this change preserves

- Choosing an existing subcategory still sets that category id.
- Choosing “— Add a new subcategory —” stores the parent category, never the sentinel, so Update cannot keep a previous subcategory that the dropdown no longer shows.
- Each dropdown’s field ids come from `useId()`, so two pickers on one page do not share `category-level-*`.
- A category with no children still hides the subcategory dropdown unless adding is allowed. That empty dropdown is not marked required.
- The name field accepts Chinese and Cantonese as well as English.
- A fetch applies only subcategories created while that request was in flight. A later fetch trusts the server.
- Pending categorisation cannot be a parent.
- Creating the subcategory uses the existing admin create route and does not change the activity until the activity editor is saved.

## Done when

- `npm run test -- tests/components/ui/cascading-category-select.test.tsx` in `apps/admin_web`.
- `npm run lint` and `npm run typecheck` in `apps/admin_web`.
- Playwright `e2e/activities.spec.ts` covers adding a subcategory and selecting it on another activity.
- `pytest tests/test_activity_category_names.py` rejects a case-variant sibling name.

## Rollback

Revert the commit. Categories created while the feature was deployed remain in the catalog.

## Open questions

None. A new subcategory is a child of the category selected on that dropdown, so another activity sees it when that activity’s subcategory list uses the same parent.
