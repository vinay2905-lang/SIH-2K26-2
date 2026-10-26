#!/bin/sh
# Container entrypoint: migrate, optionally load demo data, then serve.
set -e

# Inside a container the built-in localhost default can never work, so fail with a clear
# message instead of a connection traceback (a local backend/.env may still provide it).
if [ -z "${DATABASE_URL:-}" ] && [ ! -f .env ]; then
  echo "ERROR: DATABASE_URL is not set." >&2
  echo "Point it at a PostgreSQL database, e.g. postgresql://user:password@host:5432/dbname" >&2
  echo "On Render: deploy with the render.yaml Blueprint (New -> Blueprint), or create a" >&2
  echo "PostgreSQL database and add its Internal Database URL as DATABASE_URL on this service." >&2
  exit 1
fi

alembic upgrade head
if [ "${SEED_DEMO_DATA:-false}" = "true" ]; then
  python -m app.seed --if-empty
fi
# PORT is provided by hosts such as Render; proxy headers give real client IPs in the audit log.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" \
  --proxy-headers --forwarded-allow-ips="*"
