# Assumptions and open questions

The problem statement does not define every rule this platform needs. Where it is silent, the
prototype uses an explicit, **configurable** assumption and lists it here. None of these are
official AICTE or APAAR rules. Before any real use they must be replaced with authoritative
answers.

## Design assumptions currently in effect

| # | Assumption | Where it lives | How to change it |
|---|---|---|---|
| A1 | APAAR identifier format is a synthetic demo pattern `DEMO-APAAR-` + 6 digits, so demo IDs can never be mistaken for real ones. A 12-digit preset exists but is unconfirmed. | `system_settings.identifier_format` | Validation policy page (system admin) |
| A2 | A format check confirms only the shape of an identifier; it never establishes authenticity. | Code and UI copy | — (principle) |
| A3 | Regular-seat admissions count against approved intake; supernumerary-seat admissions count against configured supernumerary seats. Seat type is as declared by the institution. | `rules.py` (`INTAKE_EXCEEDED`, `SUPERNUMERARY_EXCEEDED`) | Rule switches; intake configuration |
| A4 | Only admissions with status `ENROLLED` count toward intake. | `system_settings.intake_policy.count_statuses` | Validation policy page |
| A5 | NRI implies Indian nationality; OCI and FN holders are not Indian nationals; NRI is exclusive of FN and OCI. | `CATEGORY_CONFLICT` rule | Can be switched off |
| A6 | Plausible age at admission is 15–60. | `system_settings.consistency` | Validation policy page |
| A7 | The academic year window starts in April (e.g. 2026-27 = 1 Apr 2026 – 31 Mar 2027). | `system_settings.consistency` | Validation policy page |
| A8 | A student is identified within an institution by APAAR ID; an admission by (student, programme, academic year). | `importer.py` | Code change (documented in [csv-import.md](csv-import.md)) |
| A9 | Two counted admissions for one APAAR ID in the same year at different institutions is a *potential* duplicate needing review — it may be legitimate (e.g. permitted dual programmes). | `CROSS_INSTITUTION_DUPLICATE` rule | Can be switched off |
| A10 | Identity details are never silently overwritten by an upload; changes go through the audited edit form. | `importer.py` | Code change |
| A11 | Institutions record verification consent on the student's behalf in the prototype. | `consent_records` | Production would capture consent from the student directly |
| A12 | Approved intake figures are synthetic and editable by central reviewer / system admin roles. | `intake_configurations.source` | Production would source them from AICTE approval data |

## Open questions for the problem-statement owner

1. What APAAR identifier format/validation rules (including any check digit) are officially specified and may be used?
2. Is an authorised APAAR/AICTE API or sandbox available? Where is the documentation and what permissions apply?
3. Which fields are mandatory for all institutions versus only some programmes or categories?
4. How is approved intake defined per programme and academic year, and where is the authoritative source?
5. How should supernumerary seats and NRI / OCI / FN categories affect intake calculations?
6. What distinguishes a duplicate admission from a legitimate transfer, re-admission or dual enrolment?
7. What may each class of external verifier see, and what consent or authorisation is required?
8. What retention and deletion rules apply to uploads, student records, verification requests and audit events?
9. Are there official data schemas or integration contracts for institution ERP/SIS and AICTE systems?
10. What performance, scale and deployment expectations apply for evaluation?

## Decisions log

| Date | Decision | Reason |
|---|---|---|
| 2026-10 | Modular monolith (FastAPI + PostgreSQL + React) | Two-developer team; one deployable; fewer moving parts |
| 2026-10 | Store APAAR IDs as keyed HMAC fingerprint + Fernet ciphertext + last four characters | Enables uniqueness and cross-institution matching without searchable plaintext |
| 2026-10 | Valid rows saved, invalid rows reported, in one transaction | Partial acceptance is more useful than all-or-nothing for large files; no partial, unreported state |
| 2026-10 | Server-side sessions in HttpOnly cookies + per-session CSRF token | Same-origin web app; avoids tokens in localStorage |
| 2026-10 | Mock identity provider behind an adapter, always labelled simulated | No authorised integration is available |
