#!/bin/sh
# Container entrypoint: migrate, optionally load demo data, then serve.
set -e
alembic upgrade head
if [ "${SEED_DEMO_DATA:-false}" = "true" ]; then
  python -m app.seed --if-empty
fi
# PORT is provided by hosts such as Render; proxy headers give real client IPs in the audit log.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" \
  --proxy-headers --forwarded-allow-ips="*"
