#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap for the siutindei monorepo.
# Prepares: Node 24 (nvm), PostgreSQL 16, Python backend deps, npm workspaces,
# generated API types, and build-time fixtures. Safe to run repeatedly.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DB_NAME="backend_test"
DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/${DB_NAME}"
export DATABASE_URL
export PATH="$HOME/.local/bin:$PATH"

echo "==> Node 24 via nvm"
export NVM_DIR="${NVM_DIR:-/home/ubuntu/.nvm}"
# shellcheck disable=SC1091
. "$NVM_DIR/nvm.sh"
nvm install 24 >/dev/null
nvm alias default 24 >/dev/null
nvm use 24 >/dev/null
node --version

echo "==> Git LFS objects"
git lfs install --local >/dev/null 2>&1 || true
git lfs pull

echo "==> PostgreSQL 16"
if ! command -v psql >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq postgresql postgresql-contrib
fi
PGHBA="$(ls /etc/postgresql/*/main/pg_hba.conf | head -n1)"
# Password auth (md5) instead of peer/scram so tests can connect over TCP.
sudo sed -i 's/^local\s\+all\s\+all\s\+peer/local   all             all                                     md5/' "$PGHBA"
sudo sed -i 's/^host\s\+all\s\+all\s\+127.0.0.1\/32\s\+scram-sha-256/host    all             all             127.0.0.1\/32            md5/' "$PGHBA"
sudo sed -i 's/^host\s\+all\s\+all\s\+::1\/128\s\+scram-sha-256/host    all             all             ::1\/128                 md5/' "$PGHBA"
sudo service postgresql start
# Wait for readiness.
for _ in $(seq 1 30); do
  if sudo -u postgres pg_isready -q; then break; fi
  sleep 1
done
sudo -u postgres psql -c "ALTER USER postgres WITH PASSWORD 'postgres';" >/dev/null
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1 \
  || sudo -u postgres createdb "${DB_NAME}"

echo "==> Python backend dependencies"
python3 -m pip install --break-system-packages --ignore-installed -q \
  -r backend/requirements.txt 'pytest>=8.0' 'pytest-cov>=5.0' 'ruff>=0.3.0' pre-commit

echo "==> Apply database migrations (schema only, no seed)"
# If a base snapshot carries an alembic_version stamped at head but is missing
# the model tables, reset the stamp so "upgrade head" recreates the schema.
HAS_CORE="$(PGPASSWORD=postgres psql -h localhost -U postgres -d "${DB_NAME}" \
  -tAc "SELECT to_regclass('public.organizations') IS NOT NULL;" 2>/dev/null || echo f)"
if [ "${HAS_CORE}" != "t" ]; then
  python3 -m alembic -c backend/db/alembic.ini stamp base >/dev/null 2>&1 || true
fi
python3 -m alembic -c backend/db/alembic.ini upgrade head

echo "==> Warm pre-commit hook environments"
python3 -m pre_commit install-hooks >/dev/null 2>&1 || true

echo "==> Sync build-time fixtures"
bash scripts/codegen/sync-activity-search-staging-fixture.sh all
bash scripts/codegen/sync-home-wizard-choices.sh

echo "==> npm install (admin_web, public_www, infrastructure)"
(cd apps/admin_web && npm ci && npm run generate:api)
(cd apps/public_www && npm ci)
(cd backend/infrastructure && npm ci)

echo "==> Install complete"
