# APAAR Student Data Platform

**Smart India Hackathon 2026 · Problem statement SIH26263 · Prototype**

A secure, APAAR-linked student-data platform for AICTE-approved institutions. Institutions
submit student-level admission records; the platform validates them with **explainable rules**,
flags possible problems for **human review**, monitors **intake compliance** in real time and
supports **consent-based verification** for authorised stakeholders.

> **Prototype with synthetic data.** Every institution, student and identifier is fictional.
> There is **no** connection to APAAR, AICTE, DigiLocker or any government system: identity
> checks go through a mock adapter and are always labelled
> **SIMULATED — NOT OFFICIAL APAAR VERIFICATION**. Not affiliated with or endorsed by AICTE.

![Central monitoring dashboard](docs/screenshots/central-dashboard.png)

## What it does

Mapped to the official flow *Institution → Upload → APAAR validation → Verification → Central
repository → Analytics & monitoring → Authorised verification*:

| | Capability |
|---|---|
| **Submit** | CSV bulk upload and single-record form; strict parsing; row-level results with reasons; downloadable error report; idempotent re-uploads |
| **Validate** | Configurable APAAR ID presence/format checks (a format check never claims authenticity); duplicates in file and across institutions; approved-intake and supernumerary overruns; NRI / OCI / FN consistency; implausible dates |
| **Explain** | Every finding states the rule, the evidence compared (identifiers masked), why it matters, the policy assumption it relies on and the recommended action |
| **Review** | Exception queue with start review / resolve / dismiss / escalate / reopen, mandatory comments, full history; findings auto-resolve when the data is fixed |
| **Monitor** | Institution and central dashboards computed live from stored records; enrolment and data-quality reports as CSV |
| **Verify** | Consent-gated lookup by APAAR ID or record reference with minimum-data disclosure; every attempt logged with its purpose |
| **Certify** | Printable admission record showing the APAAR ID alongside the institution student ID, with a verifiable reference code |
| **Protect** | Role-based access (deny by default), institution isolation, encrypted + fingerprinted identifiers, CSRF-protected cookie sessions, audit trail, configurable policy |

The official requirements are traced to code and tests in
[`docs/requirements-traceability.md`](docs/requirements-traceability.md).

## Screenshots

| | |
|---|---|
| ![Sign in](docs/screenshots/login.png) | ![Institution dashboard](docs/screenshots/institution-dashboard.png) |
| **Sign in** with one-click demo accounts | **Institution dashboard**: intake compliance, findings, uploads |
| ![Upload results](docs/screenshots/upload-results.png) | ![Finding detail](docs/screenshots/finding-detail.png) |
| **Upload results**: findings raised and rejected rows with reasons | **Explainable finding**: evidence, rule, assumption, review |
| ![Verification](docs/screenshots/verification.png) | ![Admission record](docs/screenshots/admission-record.png) |
| **Verification**: consent-gated record check, simulated provider shown separately | **Admission record** with APAAR ID and reference code |

## Quick start

### Option A — Docker Compose (one command for the whole stack)

```bash
docker compose up --build -d                    # first start also loads synthetic demo data
```

Open <http://localhost:8000>. API docs: <http://localhost:8000/api/docs>. To reset the demo data
later: `docker compose exec app python -m app.seed --reset`.

### Option B — Local development

Prerequisites: Python 3.12+, Node.js 22+, and PostgreSQL 16 (or use SQLite, below).

```bash
# 1. Database — either start PostgreSQL with Docker...
docker compose up -d db
#    ...or skip it and use SQLite by exporting:  DATABASE_URL=sqlite:///./apaar-dev.db

# 2. Backend  (http://localhost:8000, API docs at /api/docs)
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
alembic upgrade head
python -m app.seed                 # synthetic demo data; --reset wipes and reloads
uvicorn app.main:app --reload

# 3. Frontend  (http://localhost:5173, proxies /api to the backend)
cd frontend
npm install
npm run dev
```

Configuration lives in environment variables — see [`.env.example`](.env.example). In
development the app uses built-in, public identifier keys and warns about it; with
`APP_ENV=production` it refuses to start without real keys and secure cookies.

## Deploy to Render

The repository includes a [`render.yaml`](render.yaml) Blueprint: one Docker web service (API +
UI on one HTTPS origin) and a PostgreSQL database.

1. Push this repository to GitHub (already done if you are reading it there).
2. In the [Render dashboard](https://dashboard.render.com) choose **New → Blueprint**, connect
   the repository, pick the branch, and click **Apply**.
3. Wait for the first build (a few minutes). On first start the container runs the migration
   and loads the synthetic demo data; later deploys keep existing data.
4. Open `https://<your-service>.onrender.com` and sign in with a demo account.

What the Blueprint sets: `APP_ENV=production` (refuses insecure settings), `DEMO_MODE=true`
(demo accounts and sample file), `SEED_DEMO_DATA=true`, `COOKIE_SECURE=true`, `DATABASE_URL`
from the database, and two identifier keys generated once by Render. Do **not** regenerate the
keys after data exists — encrypted identifiers would no longer decrypt.

Free-plan notes: the web service sleeps after 15 idle minutes and takes about a minute to wake
(open the site shortly before a demo); a free database expires 30 days after creation and has
no backups; one free database per workspace.

**Created the web service by hand (New → Web Service) instead?** Then Render made no database
and set no variables, and the log shows `DATABASE_URL is not set` (older builds: `connection to
server at "127.0.0.1", port 5432 failed`). Either delete it and use the Blueprint, or:

1. **New → Postgres** (free, same region as the web service). Copy its **Internal Database URL**.
2. On the web service → **Environment**, add:

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | the Internal Database URL |
   | `APP_ENV` | `production` |
   | `DEMO_MODE` | `true` |
   | `SEED_DEMO_DATA` | `true` |
   | `COOKIE_SECURE` | `true` |
   | `IDENTIFIER_HMAC_KEY` | a long random string (keep it forever) |
   | `IDENTIFIER_ENCRYPTION_KEY` | another long random string (keep it forever) |

   Generate random strings with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
3. **Save, rebuild, and deploy**. The log should show the migration, `Loaded synthetic demo
   data`, then `Uvicorn running on http://0.0.0.0:10000`.

To reset the hosted demo data, run the seed locally against the database's **External Database
URL** (Render → database → Connect):

```bash
cd backend && DATABASE_URL='<external database URL>' python -m app.seed --reset
```

For a long-running or real deployment, use paid plans, keep `DEMO_MODE` off, and manage the
identifier keys in a secret store.

## Demo accounts

All passwords are `Demo@12345` (local demo only). The login page lists them; click one to fill
the form.

| Account | Role | Sees |
|---|---|---|
| `aranya.operator@demo.example` | Institution data operator | Own institution: upload, records, dashboard |
| `aranya.admin@demo.example` | Institution administrator | + review findings, issue records, audit trail |
| `kaveri.*`, `narmada.*` (operator / admin) | Same roles, other institutions | Only their own institution |
| `central.reviewer@demo.example` | Central reviewer | All institutions, escalations, intake, reports |
| `verifier@demo.example` | Authorised verifier | Verification portal only |
| `sysadmin@demo.example` | System administrator | Validation policy and intake settings |

A step-by-step presentation flow is in [`docs/demo-script.md`](docs/demo-script.md).

## Project structure

```text
backend/               FastAPI app, SQLAlchemy models, Alembic migration, tests
  app/api/v1/          Route handlers (auth, students, uploads, findings, dashboard, …)
  app/services/        Ingestion, validation rules + engine, verification adapter, reports
  app/seed.py          Synthetic demo data (loaded through the real upload pipeline)
  tests/               Unit and integration tests (SQLite or PostgreSQL)
frontend/              React + TypeScript + Vite + Tailwind single-page app
  src/features/        One folder per feature (dashboard, students, uploads, exceptions, …)
  src/components/      UI primitives and domain components
  e2e/                 Playwright end-to-end tests
docs/                  Requirements traceability, architecture, data model, API, security,
                       CSV contract, validation rules, testing results, demo script
sample-data/           CSV template and a malformed example
```

## Tech stack

- **Backend:** Python, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, PostgreSQL 16, argon2-cffi,
  cryptography (Fernet), pytest, ruff
- **Frontend:** React 19, TypeScript, Vite, Tailwind CSS 4, React Router, TanStack Query,
  React Hook Form + Zod, Recharts, lucide icons, Vitest + Testing Library, Playwright
- **Delivery:** Docker (single image serves API + UI), Docker Compose, GitHub Actions CI

## Testing

```bash
cd backend && pytest                                   # 142 tests on SQLite
TEST_DATABASE_URL=postgresql+psycopg://USER:PASS@localhost:5432/apaar_test pytest   # on PostgreSQL
ruff check . && ruff format --check .

cd frontend && npm run lint && npm run typecheck && npm test && npm run build

# End-to-end: backend running on :8000 serving the built UI, freshly seeded
cd backend && python -m app.seed --reset
cd frontend && npm run build && npx playwright install chromium && npm run e2e
```

Measured results (test counts, rule accuracy on the labelled demo fixture, upload timing) are in
[`docs/testing-and-evaluation.md`](docs/testing-and-evaluation.md). CI runs all of the above on
every push.

## What is real and what is simulated

| Real (implemented and tested) | Simulated or synthetic |
|---|---|
| Upload pipeline, validation rules, findings and review workflow, dashboards, reports, audit trail, consent gating, record references, role-based access and institution isolation | The APAAR identity provider (mock adapter with deterministic outcomes), all data, and all approved-intake figures |

## Limitations and next steps

- No authorised APAAR/AICTE integration — the adapter boundary is ready for one once access and
  documentation are available.
- Intake, category and identifier rules are **configurable assumptions** pending authoritative
  confirmation — see [`docs/assumptions-and-open-questions.md`](docs/assumptions-and-open-questions.md).
- Accounts are seeded; there is no user-management UI or multi-factor authentication yet.
- Uploads are synchronous (5,000 rows ≈ 2 s); very large files would move to a background queue.
- Possible extensions: explainable anomaly scoring to prioritise review, privacy-preserving
  cross-institution matching, PDF reports, ERP/SIS connectors.

## Documentation

| Document | Contents |
|---|---|
| [Requirements traceability](docs/requirements-traceability.md) | Official requirement → implementation → tests → status |
| [Assumptions & open questions](docs/assumptions-and-open-questions.md) | Every configurable assumption and the questions for AICTE |
| [Architecture](docs/architecture.md) | Modules, request lifecycle, upload pipeline, trust boundaries |
| [Data model](docs/data-model.md) | ER diagram, tables, identifier storage |
| [API contract](docs/api-contract.md) | Endpoints, permissions, errors, metric definitions |
| [Security model](docs/security-model.md) | Roles, permission matrix, controls, keys |
| [CSV import](docs/csv-import.md) | Columns, limits, error codes, idempotency |
| [Validation rules](docs/validation-rules.md) | Rule catalogue and finding lifecycle |
| [Testing & evaluation](docs/testing-and-evaluation.md) | Test suites and measured results |
| [Demo script](docs/demo-script.md) | Step-by-step demo for judges |
