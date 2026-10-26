# CLAUDE.md

SIH 2026 prototype for problem statement SIH26263: APAAR-linked student data management and
verification. FastAPI + PostgreSQL backend in `backend/`, React + TypeScript frontend in
`frontend/`, documentation in `docs/`.

## Non-negotiables

- Synthetic data only. Never add real student data, secrets or realistic real APAAR IDs.
  Demo identifiers use `DEMO-APAAR-######`.
- Never claim official APAAR/AICTE verification. The only identity provider is the mock in
  `backend/app/services/verification/adapter.py`; its results must carry `simulated: true` and
  the label `SIMULATED — NOT OFFICIAL APAAR VERIFICATION`.
- A format check is not authenticity. A finding is a review signal, not proof of fraud.
- Unconfirmed policy (identifier format, intake counting, category rules) stays configurable
  and is listed in `docs/assumptions-and-open-questions.md`. Do not hard-code it as official.
- Never log, return in errors, or put in URLs a full APAAR ID. Lists show masked values only.
- Every institution-scoped query must be scoped to the caller (`Principal.ensure_institution`,
  `scoped_institution_id`); out-of-scope IDs return 404. Add a tenancy test for new routes.
- Dashboards and reports must compute from stored records — no hard-coded numbers.
- Do not claim test results or metrics you have not run; update `docs/testing-and-evaluation.md`
  with measured numbers only.

## Commands

```bash
# backend (from backend/, venv active)
pip install -e ".[dev]"
alembic upgrade head && python -m app.seed --reset
uvicorn app.main:app --reload
pytest                      # SQLite; set TEST_DATABASE_URL for PostgreSQL
ruff check . && ruff format .

# frontend (from frontend/)
npm install
npm run dev                 # proxies /api to :8000
npm run lint && npm run typecheck && npm test && npm run build
npm run e2e                 # needs backend on :8000 serving the build, freshly seeded
```

## Where things live

- Record contract (CSV + form): `backend/app/services/ingestion/schema.py`
- Upserts and identity-conflict rules: `backend/app/services/ingestion/importer.py`
- Finding rules: `backend/app/services/validation/rules.py`; reconciliation: `engine.py`
- Permissions matrix: `backend/app/core/permissions.py` (mirror changes in `docs/security-model.md`)
- Schema changes: edit models, then `alembic revision --autogenerate`, review, and run
  `alembic check` (a test fails on model/migration drift)
- Frontend API types: `frontend/src/types/api.ts`; UI primitives: `frontend/src/components/ui`

Keep `docs/requirements-traceability.md` statuses honest when behaviour changes.
