# Plan: Deleted organizations stay deleted on import

**Status**: Done
**Zone**: yellow, plus a nullable column on `organization_merges`

## Goal

Deleting an organization remembers its place id, source id, and name.
A later import that matches any of those does not create the
organization or its children again.

## Non-goals

- Blocking a person from creating the same organization by hand.
- Changing merge. A merge still points the removed identity at the
  survivor, and a later import still updates that survivor.
- A new table. The existing merge row stores the identity. A null
  survivor means the organization was deleted.

## Files

- `backend/db/alembic/versions/0046_deleted_org_import.py` makes
  `survivor_org_id` nullable.
- `backend/src/app/db/models/data_quality.py` matches that column.
- `backend/src/app/services/org_delete.py` records the identity and
  matches a later import.
- `backend/src/app/db/repositories/organization.py` does not treat a
  deleted identity as a survivor.
- `backend/src/app/api/admin_crud.py` records it before the row is
  removed.
- `backend/src/app/services/import_names.py` rejects a create when the
  file matches a deleted identity.
- `backend/src/app/api/admin_imports_importer.py` reports that as
  skipped and skips children.
- `docs/api/admin.yaml`, `docs/architecture/database-schema.md`,
  `docs/architecture/data-quality.md`,
  `docs/architecture/decisions.md`, and
  `docs/architecture/lambdas.md`.
- `tests/test_deleted_org_import.py`.

## Invariants this change preserves

- A live organization still wins. Import updates or skips that row.
- A merge still forwards place id and source id to the survivor.
- Deleting the survivor keeps the merged-away place ids from being
  imported as new organizations.
- `manager_id` is still never written onto an existing organization.
- Venues and activities still disappear with the deleted organization.

## Done when

- `pytest tests/test_deleted_org_import.py tests/test_org_merge.py tests/test_alembic_revision_contract.py`
- `python3 scripts/check_python_file_length.py`
- `python3 scripts/check_openapi_routes.py`
- `pre-commit run ruff-format --all-files`

## Rollback

Revert the branch. The migration sets `survivor_org_id` back to
required after removing rows that have no survivor.

## Open questions

None. A hand-created organization with the same name is a live row,
and the next import follows that row.
