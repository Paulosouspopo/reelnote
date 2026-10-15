#!/usr/bin/env bash
# Applique les migrations sur une base Postgres jetable puis lance les tests SQL.
# Usage : PGURL=postgres://postgres:postgres@localhost:5432/postgres ./supabase/tests/run.sh
set -euo pipefail

cd "$(dirname "$0")/.."
PGURL="${PGURL:-postgres://postgres:postgres@localhost:5432/postgres}"
DB="reelnote_test_$$"

psql "$PGURL" -v ON_ERROR_STOP=1 -qc "create database $DB"
cleanup() {
  psql "$PGURL" -qc "drop database if exists $DB with (force)" >/dev/null
  # Les rôles sont globaux au cluster : on ne les supprime que s'ils ont été créés par les stubs
}
trap cleanup EXIT

TEST_URL="${PGURL%/*}/$DB"

# Les rôles anon/authenticated/service_role existent peut-être déjà (cluster partagé)
psql "$TEST_URL" -qc "do \$\$ begin
  if not exists (select from pg_roles where rolname = 'anon') then create role anon nologin; end if;
  if not exists (select from pg_roles where rolname = 'authenticated') then create role authenticated nologin; end if;
  if not exists (select from pg_roles where rolname = 'service_role') then create role service_role nologin bypassrls; end if;
end \$\$;"

grep -v '^create role' tests/00_supabase_stubs.sql | psql "$TEST_URL" -v ON_ERROR_STOP=1 -q

for migration in migrations/*.sql; do
  echo "→ $migration"
  psql "$TEST_URL" -v ON_ERROR_STOP=1 -q -f "$migration"
done

for test in tests/*.test.sql; do
  echo "→ $test"
  psql "$TEST_URL" -v ON_ERROR_STOP=1 -q -f "$test"
done
