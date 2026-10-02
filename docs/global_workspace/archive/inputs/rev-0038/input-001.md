We get this error:

(.venv) $ PGPASSWORD="${POSTGRES_PASSWORD:-}" pg_dump --no-password \
  --host="${POSTGRES_HOST:-}" --port="${POSTGRES_PORT:-5432}" \
  --username="${POSTGRES_USER:-postgres}" --dbname="${POSTGRES_DB:-clara2}" \
  --format=custom --file="$CLARA_PARTICIPATION_BACKUP/database.dump"> > > 
pg_dump: error: aborting because of server version mismatch
pg_dump: detail: server version: 18.3; pg_dump version: 16.15 (Ubuntu 16.15-0ubuntu0.24.04.1)
