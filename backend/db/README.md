# Database migrations (Alembic)

This directory contains Alembic migrations for the Aurora PostgreSQL
schema.

## Requirements

- Python 3.12+
- The backend dependencies installed (`backend/requirements-core.txt`
  pins `alembic`, `sqlalchemy`, and `psycopg` 3).

## Run migrations

Set your database URL (UTC only). Use the `psycopg` (v3) driver and add
`?sslmode=require` for any remote database:

```
export DATABASE_URL="postgresql+psycopg://user:pass@host:5432/dbname"
```

Apply migrations:

```
alembic -c backend/db/alembic.ini upgrade head
```

Generate a new migration:

```
alembic -c backend/db/alembic.ini revision -m "add new table"
```

## Seed data

Sample data is available in `backend/db/seed/seed_data.sql`.
To apply:

```
psql "$DATABASE_URL" -f backend/db/seed/seed_data.sql
```
