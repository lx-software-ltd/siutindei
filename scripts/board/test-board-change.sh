#!/usr/bin/env bash
set -euo pipefail
exec > >(tee "${RUNNER_TEMP}/board-test.log") 2>&1
if git diff --quiet origin/staging -- \
  && [ -z "$(git ls-files --others --exclude-standard)" ]; then
  echo "No changes from staging; skip repo tests"
  exit 0
fi
if git diff --name-only origin/staging -- backend tests \
  | grep -q . \
  || git ls-files --others --exclude-standard -- backend tests | grep -q .; then
  python -m pip install --upgrade pip
  if [ -f backend/dev-requirements.txt ]; then
    python -m pip install -r backend/dev-requirements.txt
  else
    python -m pip install -r backend/requirements.txt
    python -m pip install 'pytest>=8.0'
  fi
  python -m alembic -c backend/db/alembic.ini upgrade head
  python -m pytest tests backend --tb=short -q
else
  echo "No backend/tests changes; Flutter and Node stay on PR CI (test.yml)."
fi
