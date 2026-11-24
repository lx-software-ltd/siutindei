#!/usr/bin/env bash
set -euo pipefail
export DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/backend_test"
export TEST_DATABASE_URL="$DATABASE_URL"
python -m pip install --upgrade pip
if [ -f backend/dev-requirements.txt ]; then
  python -m pip install -r backend/dev-requirements.txt
else
  python -m pip install -r backend/requirements.txt
  python -m pip install 'pytest>=8.0' 'pytest-cov>=5.0'
fi
python -m alembic -c backend/db/alembic.ini upgrade head
python -m pytest tests backend --cov=app --cov-report=xml:coverage.xml --cov-report=term-missing --cov-fail-under=35
