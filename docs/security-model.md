# Security and privacy model

These controls are appropriate for a prototype that handles synthetic data. Production use
would additionally need legal, privacy and security review; adding controls does not by itself
establish regulatory compliance.

## Roles (prototype definitions, not official AICTE roles)

| Role | Scope | Purpose |
|---|---|---|
| `institution_operator` | Own institution | Submits and maintains records; uploads; records consent; runs identity checks |
| `institution_admin` | Own institution | Everything an operator can do, plus reviews findings, issues record references, reads the institution's audit trail |
| `central_reviewer` | All institutions | Monitoring, resolving escalated and central-only findings, approved intake, verification |
| `authorized_verifier` | Verification only | Consent-gated record verification with minimum data |
| `system_admin` | Configuration | Validation policy and approved intake; no access to student records |

## Permission matrix

Deny by default. Source of truth: `backend/app/core/permissions.py`.

| Permission | Operator | Inst. admin | Central | Verifier | Sys admin |
|---|:-:|:-:|:-:|:-:|:-:|
| students.read | ✓ | ✓ | ✓ | | |
| students.write | ✓ | ✓ | | | |
| uploads.create | ✓ | ✓ | | | |
| uploads.read | ✓ | ✓ | ✓ | | |
| findings.read | ✓ | ✓ | ✓ | | |
| findings.review | | ✓ | ✓ | | |
| programmes.read | ✓ | ✓ | ✓ | | ✓ |
| intake.manage | | | ✓ | | ✓ |
| institutions.read | | | ✓ | | ✓ |
| dashboard.institution | ✓ | ✓ | | | |
| dashboard.central | | | ✓ | | |
| reports.export | ✓ | ✓ | ✓ | | |
| verification.identity_check | ✓ | ✓ | ✓ | | |
| verification.lookup | | | ✓ | ✓ | |
| consent.manage | ✓ | ✓ | | | |
| records.issue | | ✓ | | | |
| audit.read | | ✓ (own) | ✓ | | ✓ |
| settings.manage | | | | | ✓ |

Finding actions are further limited by state and rule: intake and cross-institution findings
are resolved only by central reviewers; institution admins can comment or escalate them.

## Controls

| Area | Control | Where |
|---|---|---|
| Passwords | Argon2 (argon2-cffi); constant-time path for unknown emails | `core/security.py` |
| Sessions | Random 256-bit token in an HttpOnly, SameSite=Lax cookie (`Secure` required in production); only a SHA-256 hash is stored; 8 h expiry; revoked on logout | `api/v1/auth.py`, `api/deps.py` |
| CSRF | Per-session token required in `X-CSRF-Token` on every state-changing request | `api/deps.py` |
| Brute force | 5 failed logins per email per 15 minutes → 429 (in-process limiter) | `core/ratelimit.py` |
| Authorisation | Permission dependency on every route; denials audited | `api/deps.py` |
| Tenant isolation | Every institution query scoped; out-of-scope IDs return 404 | services, routes; `tests/integration/test_tenancy.py` |
| Identifier protection | Keyed HMAC fingerprint + Fernet ciphertext + last four; masked in all lists; full ID only on the audited record view | `core/identifiers.py` |
| No identifiers in URLs | Lookups by APAAR ID use POST bodies | `/students/lookup`, `/verification/lookup` |
| Logging | Audit writer drops forbidden keys; errors never echo submitted values; tests scan the audit log for identifiers | `services/audit.py` |
| Input handling | Pydantic request schemas (no mass assignment), ORM parameterisation, CSV size/row/encoding limits, filename sanitising | `schemas`, `ingestion/` |
| Output handling | CSV formula-injection protection; consistent error envelope without stack traces | `services/reporting.py`, `core/errors.py` |
| Headers | CSP `default-src 'self'`, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store` on API | `main.py` |
| Consent | Append-only consent history; verification discloses details only with consent on record | `services/records.py` |
| Simulated provider | Results always carry `simulated: true` and the label **SIMULATED — NOT OFFICIAL APAAR VERIFICATION** | `services/verification/adapter.py` |

## Keys

| Variable | Purpose | Notes |
|---|---|---|
| `IDENTIFIER_HMAC_KEY` | Fingerprints and record digests | Rotating it invalidates fingerprints; needs a re-keying migration |
| `IDENTIFIER_ENCRYPTION_KEY` | Fernet key for identifier ciphertext | Generate with `Fernet.generate_key()` |

In development, built-in **public** dev keys are used so a fresh checkout runs without setup;
the app logs a warning. With `APP_ENV=production` the app refuses to start on dev keys or
without `COOKIE_SECURE=true`. Real deployments should hold keys in a managed secret store.

## Known limitations

- The login limiter is per process; multiple instances need a shared store.
- No multi-factor authentication or user-management UI (accounts are seeded).
- Consent is recorded by the institution on the student's behalf (prototype simplification).
- Audit events are append-only at application level; database-level immutability (e.g. WORM
  storage or restricted grants) is not configured.
