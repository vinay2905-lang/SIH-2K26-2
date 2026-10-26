# Architecture

A modular monolith: one FastAPI application, one PostgreSQL database, one React single-page
app. In production-like runs FastAPI also serves the built frontend, so the browser talks to a
single origin (no CORS, first-party cookies).

```text
Browser — React + TypeScript (Vite, Tailwind, TanStack Query, React Router)
   │  HTTPS, JSON, HttpOnly session cookie + X-CSRF-Token header
   ▼
FastAPI application (backend/app)
   ├── api/v1/*            Route handlers: auth, students, uploads, findings, dashboard,
   │                       reports, verification, programmes, admin (audit, settings), demo
   ├── api/deps.py         Session + CSRF check, permission dependency, institution scoping
   ├── core/               Config, password hashing, identifier protection, errors, roles
   ├── services/
   │   ├── ingestion/      CSV parser, record contract, importer (idempotent upserts), uploads
   │   ├── validation/     Rule catalogue + engine (dedupe, auto-resolve, review history)
   │   ├── verification/   Provider adapter interface + mock provider (SIMULATED)
   │   ├── dashboard.py    Metrics computed from persisted records
   │   ├── records.py      Verifiable record references, consent helpers
   │   ├── reporting.py    CSV export with formula-injection protection
   │   ├── settings.py     Configurable policy (identifier format, intake counting, rules)
   │   └── audit.py        Append-only audit writer (drops forbidden keys)
   └── seed.py             Synthetic demo data loaded through the real upload pipeline
   ▼
PostgreSQL 16 (SQLite supported for zero-setup runs and tests)
```

## Request lifecycle

1. Middleware assigns a request ID and adds security headers (CSP, `X-Frame-Options: DENY`,
   `nosniff`, `no-store` for API responses).
2. `get_principal` resolves the session cookie (stored hashed), rejects expired or revoked
   sessions, and for state-changing methods requires a matching `X-CSRF-Token`.
3. `require(permission)` enforces the role's permission (deny by default); denials are audited.
4. Services scope every institution-level query to the caller's institution. Records of other
   institutions respond **404** so their existence is not revealed.
5. Errors use one envelope: `{"error": {"code", "message", "details", "request_id"}}`; stack
   traces and SQL never reach the client.

## Upload pipeline

```text
CSV bytes ─► parse (UTF-8, headers, shape, limits) ─► per-row validation (schema.py)
         ─► context checks (institution, programme, in-file duplicates, identity conflicts)
         ─► prefetch existing students/admissions ─► upsert (created / updated / unchanged)
         ─► row results ─► rule engine for the institution + cross-institution rule
         ─► batch summary ─► single COMMIT  (on any unexpected error: ROLLBACK + FAILED batch)
```

## Trust boundaries

| Boundary | Control |
|---|---|
| Browser ↔ API | Session cookie (HttpOnly, SameSite=Lax, Secure in production), CSRF token, server-side validation |
| Institution ↔ institution | Query scoping in every service; 404 for out-of-scope IDs; tests prove isolation |
| Central data ↔ institution | Restricted evidence (other institutions involved) only returned to central roles |
| Platform ↔ external identity provider | Adapter interface; only a mock implementation exists and every result is marked simulated |
| Platform ↔ verifiers | Consent check per student; minimum fields disclosed; every attempt logged with purpose |

## Frontend

Feature folders under `frontend/src/features` (auth, dashboard, students, uploads, exceptions,
programmes, reports, verification, audit, settings). Shared UI primitives live in
`components/ui`, domain badges in `components/domain.tsx`, the API client in `lib/api.ts`.
Navigation and routes are permission-aware, but the server enforces every permission.

### Charts

Charts follow a validated data-visualisation palette: single-series bars use one hue; the two
upload-quality series use categorical slots 1–2 (blue `#2a78d6`, orange `#eb6834`), validated
for colour-vision deficiency separation and contrast. Status colours (good / critical) always
come with an icon and text label. Every chart has a tooltip and a data-table fallback.

## Scaling notes (not needed for the prototype)

- Uploads are processed synchronously; 5,000 rows take about 2 s on a 4-core dev container.
  Very large files would move to a background job queue.
- The login rate limiter is in-process; multiple instances would need a shared store.
- Dashboards compute on request; at national scale they would use pre-aggregated tables.
