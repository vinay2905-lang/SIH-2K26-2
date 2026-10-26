# Testing and evaluation

All numbers below were **measured** in this repository's development environment on
26 Oct 2026 (Linux container, 4 vCPU, PostgreSQL 16 on localhost, Python 3.13, Node 22).
Re-run the commands to reproduce them; numbers will differ on other hardware.

## Automated test suites

| Suite | Command | Result |
|---|---|---|
| Backend unit + integration (SQLite) | `cd backend && pytest` | 142 passed |
| Backend unit + integration (PostgreSQL) | `TEST_DATABASE_URL=postgresql+psycopg://…/apaar_test pytest` | 142 passed |
| Backend lint/format | `ruff check . && ruff format --check .` | clean |
| Frontend unit/component | `cd frontend && npm test` | 13 passed |
| Frontend lint + typecheck + build | `npm run lint && npm run typecheck && npm run build` | clean |
| End-to-end (Playwright, real stack) | `npm run e2e` (after reseeding) | 2 passed |

Every backend test starts from a fresh copy of a migrated, seeded template database (built with
the real Alembic migration), so tests are isolated and order-independent.

### What the tests cover

| Area | Examples |
|---|---|
| Record contract | Every field rule; normalisation; identifier never echoed in messages |
| CSV parsing | BOM, blank rows, header case, duplicate/missing/unknown columns, non-UTF-8, binary, row limit, broken quoting |
| Rules | Category conflicts, age boundaries, academic-year windows for every start month, rule metadata completeness |
| Upload flow | Planted-problem file end to end; idempotent repeat upload; identity protection; malformed file writes nothing; size/type guards; wrong-institution rows |
| Findings | Explainable detail; operator cannot act; comment required; central-only resolution; escalation; auto-resolve after fixing data; dismissed findings not re-raised; raising intake resolves overrun |
| Security | HttpOnly cookie; generic login errors; rate limiting; CSRF; session revocation; hashed session tokens; security headers; 13 role/route denials; cross-institution reads and writes return 404 and change nothing; denied access audited |
| Privacy | No APAAR identifier pattern in error reports, audit details, batch metadata, list or detail responses; ciphertext and fingerprints only at rest |
| Verification | Consent gating; withdrawal stops disclosure; format failure skips provider; simulated label on every provider result; reference valid → changed → superseded → not found |
| Reports & dashboards | Dashboard counts equal database queries; CSV equals JSON totals; central dashboard reconciles with the report; institution scoping of reports |
| Deployment | `postgres://` URL normalisation; demo mode independent of production hardening; any secret usable as encryption key; seed skips existing data on restart |
| Settings & migrations | Invalid regex rejected; disabled rules leave findings; stricter thresholds raise findings; identifier format applies to new records; migration upgrade/check/downgrade with no model drift |

## Rule correctness on the labelled demo fixture

The demo upload for *Aranya Institute of Technology (Demo)* (`GET /api/v1/demo/sample-upload.csv`)
contains 171 rows: 160 generated valid rows and 11 rows carrying planted problems (one
problem — a student admitted to two programmes — spans two rows). The accepted rows also push
one programme over its approved intake, giving 11 planted problems in total.

| Planted problem | Expected outcome | Measured |
|---|---|---|
| Missing APAAR ID | Row rejected `IDENTIFIER_MISSING` | ✓ |
| Malformed APAAR ID | Row rejected `IDENTIFIER_FORMAT_INVALID` | ✓ |
| Exact duplicate row | Row rejected `DUPLICATE_IN_FILE` | ✓ |
| Date in `DD/MM/YYYY` | Row rejected `INVALID_DATE` | ✓ |
| Unknown programme | Row rejected `UNKNOWN_PROGRAMME` | ✓ |
| Invalid seat type | Row rejected `INVALID_VALUE` | ✓ |
| Programme over intake (65 vs 60) | `INTAKE_EXCEEDED` with counted 65, limit 60, excess 5 | ✓ |
| Same APAAR ID enrolled at another institution | `CROSS_INSTITUTION_DUPLICATE` raised for both institutions | ✓ |
| NRI + Foreign National with IN nationality | `CATEGORY_CONFLICT` | ✓ |
| Same student in two programmes, same year | `MULTIPLE_ACTIVE_ADMISSIONS` | ✓ |
| Age 13 at admission | `AGE_AT_ADMISSION` | ✓ |

Result: **11 of 11 planted problems detected; 0 unexpected findings or rejections on the clean
rows** (asserted exactly by `test_demo_upload_end_to_end`). This is a single synthetic fixture
designed by the team; it demonstrates the rules behave as specified, not real-world accuracy.

## Upload processing time

Measured through the HTTP API against PostgreSQL, clean synthetic rows, including validation,
persistence and the full rule run (`server_processing_ms` from the batch record):

| Rows | Server processing | Wall time (client) |
|---|---|---|
| 171 (demo file; 3 runs) | 77–82 ms | — |
| 1,000 | 491 ms | 535 ms |
| 5,000 | 2,004 ms | 2,059 ms |

An earlier version issued several queries per row and took 13.4 s for 5,000 rows; bulk
prefetching of existing students and admissions reduced this about 6.7×.

## Not yet measured

- Duplicate-detection precision/recall against a labelled real-world-like dataset (needs labelled data).
- Behaviour at national scale (millions of records) and under concurrent uploads.
- Accessibility audit with assistive technology (keyboard and ARIA basics are in place, not formally audited).
