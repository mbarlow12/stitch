#!/bin/sh
set -eu

: "${POSTGRES_DB:?POSTGRES_DB must be set}"
: "${POSTGRES_USER:?POSTGRES_USER must be set}"
: "${STITCH_MIGRATOR_PASSWORD:?STITCH_MIGRATOR_PASSWORD must be set}"
: "${STITCH_APP_PASSWORD:?STITCH_APP_PASSWORD must be set}"

escape_sql_literal() {
  printf '%s' "$1" | sed "s/'/''/g"
}

if [ -z "$(
  psql -tA -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    -c "SELECT 1 FROM pg_roles WHERE rolname='stitch_migrator'"
)" ]; then
  MIG_ESCAPED=$(escape_sql_literal "$STITCH_MIGRATOR_PASSWORD")
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    -c "CREATE ROLE stitch_migrator LOGIN PASSWORD '$MIG_ESCAPED';"
else
  echo "stitch_migrator already exists"
fi

if [ -z "$(
  psql -tA -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    -c "SELECT 1 FROM pg_roles WHERE rolname='stitch_app'"
)" ]; then
  APP_ESCAPED=$(escape_sql_literal "$STITCH_APP_PASSWORD")
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    -c "CREATE ROLE stitch_app LOGIN PASSWORD '$APP_ESCAPED';"
else
  echo "stitch_app already exists"
fi

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -c "GRANT CONNECT ON DATABASE \"$POSTGRES_DB\" TO stitch_migrator;"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -c "GRANT CONNECT ON DATABASE \"$POSTGRES_DB\" TO stitch_app;"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -c "GRANT USAGE ON SCHEMA public TO stitch_migrator;"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -c "GRANT USAGE ON SCHEMA public TO stitch_app;"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -c "GRANT CREATE ON SCHEMA public TO stitch_migrator;"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -c "ALTER DEFAULT PRIVILEGES FOR ROLE stitch_migrator IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO stitch_app;"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -c "ALTER DEFAULT PRIVILEGES FOR ROLE stitch_migrator IN SCHEMA public GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO stitch_app;"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -c "ALTER DEFAULT PRIVILEGES FOR ROLE stitch_migrator IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO stitch_app;"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -c "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO stitch_app;"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -c "GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO stitch_app;"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -c "REVOKE CREATE ON SCHEMA public FROM PUBLIC;"
