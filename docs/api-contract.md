# API contract

Base path `/api/v1`. Interactive OpenAPI documentation is served at **`/api/docs`** (the
schema at `/api/openapi.json` is generated from the code and is the source of truth).

## Conventions

- **Authentication:** `POST /auth/login` sets an HttpOnly `apaar_session` cookie and returns a
  `csrf_token`. Every `POST`/`PUT`/`PATCH`/`DELETE` must send it as `X-CSRF-Token`.
- **Errors:** `{"error": {"code": "...", "message": "...", "details": ..., "request_id": "..."}}`.
  Validation errors list `details: [{"field", "code", "message"}]` and never echo submitted values.
- **Status codes:** 401 unauthenticated / session expired, 403 missing permission or bad CSRF,
  404 not found *or outside your institution*, 409 conflict / action not allowed in the current
  state, 413 file too large, 415 wrong file type, 422 validation, 429 rate limited.
- **Pagination:** `?page=1&page_size=25` (max 100) → `{"items", "total", "page", "page_size"}`.
- **Scoping:** institution users are always pinned to their institution; an `institution_id`
  query parameter is ignored for them.

## Endpoints

| Method & path | Permission | Purpose |
|---|---|---|
| `POST /auth/login` | — | Sign in (rate-limited: 5 failures / 15 min per email) |
| `POST /auth/logout` | session | Revoke the session |
| `GET /auth/me` | session | Current user, permissions, CSRF token |
| `GET /meta/public` | — | App identity; demo accounts only when `APP_ENV` ≠ production |
| `GET /meta/config` | session | CSV columns, allowed values, identifier format label, academic years |
| `GET /rules` | session | Rule catalogue with explanations and assumptions |
| `GET /institutions` | `institutions.read` | Institutions with counts |
| `GET /programmes` | `programmes.read` | Programmes with intake configurations |
| `PUT /programmes/{id}/intake/{year}` | `intake.manage` | Set approved intake; re-runs rules |
| `GET /students` | `students.read` | Search/filter students (masked identifiers) |
| `POST /students/lookup` | `students.read` | Find by full APAAR ID (body, never URL); audited |
| `POST /students` | `students.write` | Submit one record (same validation as CSV) |
| `GET /students/{id}` | `students.read` | Detail: admissions, consent, checks, findings |
| `PATCH /students/{id}` | `students.write` | Edit identity fields with a reason; audited |
| `PATCH /admissions/{id}` | `students.write` | Edit admission fields with a reason; re-runs rules |
| `POST /students/{id}/consent` | `consent.manage` | Record consent granted / withdrawn |
| `POST /students/{id}/identity-check` | `verification.identity_check` | Simulated APAAR check |
| `POST /admissions/{id}/certificate` | `records.issue` | Issue/reuse record reference; returns printable record with full APAAR ID; audited |
| `GET /uploads/template.csv` | session | CSV template |
| `GET /demo/sample-upload.csv` | `uploads.create` | Demo file with planted problems (demo mode only) |
| `POST /uploads/students` | `uploads.create` | Multipart CSV upload → batch summary |
| `GET /uploads` | `uploads.read` | Upload history |
| `GET /uploads/{id}` | `uploads.read` | Batch summary |
| `GET /uploads/{id}/rows` | `uploads.read` | Row results (`?status=rejected`) |
| `GET /uploads/{id}/errors.csv` | `uploads.read` | Error report (no identifiers) |
| `GET /findings` | `findings.read` | Queue (`status=active|open|in_review|escalated|closed|all`, category, severity, rule, year, student, batch) |
| `GET /findings/summary` | `findings.read` | Counts by status, category, severity |
| `GET /findings/{id}` | `findings.read` | Detail with evidence, rule explanation, history, allowed actions |
| `POST /findings/{id}/actions` | `findings.review` | `start_review`, `resolve`, `dismiss`, `escalate`, `reopen`, `comment` |
| `GET /dashboard/institution` | `dashboard.institution` | Institution metrics for a year |
| `GET /dashboard/central` | `dashboard.central` | Cross-institution metrics for a year |
| `GET /reports/enrolment(.csv)` | `reports.export` | Enrolment vs approved intake |
| `GET /reports/data-quality(.csv)` | `reports.export` | Findings by rule and status; upload acceptance |
| `POST /verification/lookup` | `verification.lookup` | Verify by APAAR ID + purpose (consent-gated; provider simulated) |
| `POST /verification/reference` | `verification.lookup` | Verify a record reference code |
| `GET /verification/attempts` | `verification.lookup` | History (verifiers see only their own) |
| `GET /audit-events` | `audit.read` | Audit trail (institution admins see only their institution) |
| `GET /settings` / `PUT /settings` | `settings.manage` | Validation policy; saving re-validates all records |
| `GET /api/health` | — | Liveness + database check |

## Example: upload

```http
POST /api/v1/uploads/students
Cookie: apaar_session=…
X-CSRF-Token: …
Content-Type: multipart/form-data; boundary=…
```

```json
{
  "id": "…", "status": "partial", "total_rows": 171,
  "created_rows": 165, "updated_rows": 0, "unchanged_rows": 0, "rejected_rows": 6,
  "findings_opened": 5, "file_errors": [], "warnings": [], "processing_ms": 82
}
```

## Metric definitions (dashboards and reports)

| Metric | Definition |
|---|---|
| Active enrolments | Admissions in the year whose status is a counted status (default `ENROLLED`). A student in two programmes counts twice. |
| Distinct students | Students with at least one counted admission in the year |
| Approved intake | Sum of configured approved intake for the year |
| Utilisation | Regular-seat active enrolments ÷ approved intake |
| Open findings | Findings that are open, in review or escalated (all years) |
| Acceptance rate | Accepted rows ÷ processed rows across uploads |
