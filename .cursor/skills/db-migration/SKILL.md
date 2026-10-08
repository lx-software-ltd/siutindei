---
name: db-migration
description: Add or change an Alembic revision, update seed data, and refresh the schema doc.
---

# Database migration

1. Add a revision whose id is at most 32 characters and matches `NNNN_short_description`.
2. Assess `backend/db/seed/seed_data.sql` and answer all of these in the PR:
   - existing seed SQL still runs
   - new NOT NULL or CHECK columns have seed values
   - renamed or dropped columns are reflected in the seed
   - new tables are either seeded or explicitly left empty
   - enum or allowed-value changes are valid in seed rows
   - foreign keys and cascades still insert in a valid order
3. Update `docs/architecture/database-schema.md` when a table or column changes.
4. Confirm `alembic upgrade head` then the seed file. Integration coverage runs in CI with `DATABASE_URL`.

## Done

`pytest tests/test_alembic_revision_contract.py` passes, and the PR states the seed decision.
