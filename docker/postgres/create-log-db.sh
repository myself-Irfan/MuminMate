#!/bin/sh
set -e

# The image creates only POSTGRES_DB.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v log_db="$LOG_POSTGRES_DB" <<'SQL'
SELECT format('CREATE DATABASE %I', :'log_db')
\gexec
SQL
