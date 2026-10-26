# Requirements traceability — SIH26263

Each official requirement from the problem statement, where it is implemented, how it is
verified, and its status. Status values: `planned`, `in progress`, `implemented`, `verified`
(implemented **and** covered by passing automated tests). Status reflects this repository as
committed; it is not inferred.

| ID | Official requirement | Implementation | Acceptance / evidence | Tests | Status |
|---|---|---|---|---|---|
| REQ-01 | Secure platform/API for institutions to upload and update student-level data using APAAR ID as the unique identifier | `POST /api/v1/uploads/students` (CSV), `POST /api/v1/students` (form), `PATCH /students/{id}`, `PATCH /admissions/{id}`; students keyed by keyed-HMAC fingerprint of the APAAR ID; idempotent upserts | Institution users can submit and update only their own institution's records; repeat uploads do not duplicate | `test_upload_flow.py`, `test_records_reports_settings.py::test_manual_record_entry`, `test_tenancy.py` | verified |
| REQ-02 | Fields: approved intake, actual enrolment, supernumerary seats, NRI, OCI, FN status, other relevant info | `IntakeConfiguration` (approved intake, supernumerary seats per programme-year); admission fields `seat_type`, `nri_category`, `oci_status`, `foreign_national_status`, `nationality`, `enrolment_status`; actual enrolment computed from records | Dashboard and report show approved intake vs actual enrolment and category counts | `test_dashboard_matches_database_counts`, `test_central_dashboard_reconciles_with_reports` | verified |
| REQ-03 | Automated validation: duplicates, invalid/missing APAAR IDs, intake overrun, inconsistencies, cross-institution duplicates | Row validation (`services/ingestion/schema.py`, `importer.py`) and rule engine (`services/validation/rules.py`, `engine.py`) — see [validation-rules.md](validation-rules.md) | Every planted problem in the demo file is detected with a reason and evidence | `test_demo_upload_end_to_end`, `tests/unit/test_record_schema.py`, `test_rules_and_provider.py` | verified |
| REQ-04 | Real-time dashboards for AICTE and institutions | `GET /dashboard/institution`, `GET /dashboard/central`; computed on request from persisted records | Figures reconcile with database counts and reports | `test_dashboard_matches_database_counts`, `test_central_dashboard_reconciles_with_reports` | verified |
| REQ-05 | Secure verification for authorised stakeholders (AICTE, institutions, employers, regulators) | `authorized_verifier` and `central_reviewer` roles; `POST /verification/lookup` and `/verification/reference`; consent-gated, minimum-data disclosure; mock identity provider clearly labelled **SIMULATED** | Details disclosed only with consent; every attempt logged with purpose; no raw identifiers stored | `test_verification_and_records.py` | verified (identity provider simulated) |
| REQ-06 | Verifiable student records linked to academic identity | `VerifiableRecord` with reference code and keyed integrity digest; reference check reports valid / changed since issue / superseded / not found | A changed record no longer verifies as unchanged; reissue supersedes the old reference | `test_certificate_and_reference_check` | verified (prototype integrity check, not an official credential) |
| REQ-07 | Integration/API with institutional and AICTE systems | Versioned REST API under `/api/v1`, OpenAPI at `/api/docs`, CSV contract, provider adapter interface (`services/verification/adapter.py`) | ERP/SIS can push CSV or JSON; adapter boundary ready for an authorised provider | OpenAPI generated; API covered by integration tests | implemented (no external system connected) |
| REQ-08 | Security, privacy, authentication, RBAC, audit trails, consent | HttpOnly session cookies + CSRF, argon2 password hashing, rate-limited login, deny-by-default permission matrix, institution isolation, identifier encryption + masking, append-only audit log, consent history — see [security-model.md](security-model.md) | Cross-institution access returns 404; identifiers never appear in logs, URLs or error reports | `test_auth.py`, `test_tenancy.py`, `test_error_report_and_audit_never_contain_identifiers` | verified |
| REQ-09 | Reports for policy-making, accreditation, monitoring, regulation | `GET /reports/enrolment(.csv)`, `GET /reports/data-quality(.csv)` with period, scope, timestamp, definitions; spreadsheet formula-injection protection | CSV totals equal the JSON report and dashboard | `test_enrolment_report_csv_matches_json_and_is_audited`, `test_csv_formula_injection_is_neutralised` | verified |
| REQ-10 | Print/display APAAR ID alongside student ID on certificates | Printable admission record (`/admissions/{id}/certificate`) showing institution student ID and full APAAR ID with reference code; access limited to institution administrators and audited | Full identifier appears only on this audited view | `test_certificate_and_reference_check`, `test_certificate_requires_institution_admin` | verified |

## Expected flow coverage

`Institution → Student Data Upload → APAAR Validation → Data Verification → Central Repository → Analytics & Monitoring → Authorized Verification`

| Step | Where in the product |
|---|---|
| Institution | Institution-scoped accounts (operator, admin) |
| Student data upload | Uploads page / CSV API / record form |
| APAAR validation | Configurable presence + format checks (format only — never treated as authenticity) |
| Data verification | Rule engine findings + human review queue; optional simulated identity check |
| Central repository | PostgreSQL, one schema, per-institution isolation |
| Analytics & monitoring | Institution and central dashboards, reports |
| Authorised verification | Verifier portal (consent-gated) and record reference checks |
