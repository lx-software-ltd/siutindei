# Plan: Deleted organizations stay deleted on import

**Status**: Done
**Zone**: yellow, plus `backend/db/alembic/versions/0046_deleted_org_import.py`

The nullable survivor column and the `kind` column were requested when
the review fixes were asked for. That request is the approval to edit
this unreleased revision.

## Goal

An admin delete remembers an organization so a later import does not
create it again. A manager delete does not. An admin can forget one
remembered identity and allow that import again.

## Non-goals

- Blocking a person from creating the same organization by hand.
- Changing merge. A merge still points the removed identity at the
  survivor, and a later import still updates that survivor.
- A new table. `organization_merges.kind` is `merge` or `delete`.

## Files

- `backend/db/alembic/versions/0046_deleted_org_import.py` makes
  `survivor_org_id` nullable and adds `kind`. Downgrade refuses while
  deletion rows exist.
- `backend/src/app/db/models/data_quality.py` matches those columns.
- `backend/src/app/services/org_delete.py` records identity only,
  matches a later import in SQL, lists deletions, and forgets one.
- `backend/src/app/db/repositories/organization.py` does not treat a
  deletion as a survivor.
- `backend/src/app/api/admin_crud.py` records a delete only for an
  admin.
- `backend/src/app/api/admin_deleted_organizations.py` lists and
  forgets remembered identities.
- `backend/src/app/api/admin.py` dispatches that route.
- `backend/src/app/services/import_names.py` rejects a create when the
  file matches a deleted identity.
- `backend/src/app/api/admin_imports_importer.py` reports that as
  skipped and skips children.
- `apps/admin_web` Data quality tab "Deleted".
- `docs/api/admin.yaml` and the architecture docs listed below.
- `tests/test_deleted_org_import.py`.

## Match rules

- Place id matches that place id.
- Source id matches only when the catalog source is the same.
- A name, including a name the organization used before it was
  renamed, matches only when the file has no place id and no source
  id, or the deleted organization had neither.
- A live organization still wins.

## Stored identity

Name, earlier names, place id, source, and source id. No email, phone,
or manager id. `kind` is `delete`. `merged_by` and `merged_at` are the
actor and time for both merges and deletes.

## Invariants this change preserves

- A live organization still wins. Import updates or skips that row.
- A merge still forwards place id and source id to the survivor.
- Deleting the survivor keeps the merged-away place ids from being
  imported as new organizations.
- `manager_id` is still never written onto an existing organization.
- Venues and activities still disappear with the deleted organization.

## Done when

- `pytest tests/test_deleted_org_import.py tests/test_org_merge.py tests/test_alembic_revision_contract.py tests/test_admin_imports.py tests/test_import_names.py`
- `python3 scripts/check_python_file_length.py`
- `python3 scripts/check_openapi_routes.py`
- `node scripts/check-lambda-docs.mjs`
- `pre-commit run ruff-format --all-files`
- Admin web lint, typecheck, and the Deleted tab Playwright spec
- `alembic upgrade head` then seed on a fresh database; downgrade
  refuses while a deletion row exists

## Rollback

Forget the remembered identities, or export and delete
`organization_merges` rows with `kind = 'delete'`. Then
`alembic downgrade 0045_hk_neighbourhoods` drops `kind` and requires
`survivor_org_id` again. Downgrade raises while any deletion row
exists, so a rollback cannot drop those identities silently.

## Open questions

None.
