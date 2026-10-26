# CSV import

Download the template from the Uploads page or `GET /api/v1/uploads/template.csv`. In demo mode
the **Demo sample file** button produces a realistic file with deliberately planted problems.
A copy of the template lives in [`sample-data/`](../sample-data).

## File requirements

- UTF-8 (a byte-order mark is fine). Excel: *Save As → CSV UTF-8*.
- `.csv` extension; at most **5 MB** and **5,000 data rows** (configurable).
- First non-blank row is the header. Header names are trimmed and compared case-insensitively;
  nothing else is guessed.
- Blank rows are skipped and counted. Unknown columns are ignored with a warning.

## Columns

| Column | Required | Rule |
|---|---|---|
| `institution_code` | yes | Must equal your institution's code |
| `programme_code` | yes | Must be a programme configured for your institution |
| `academic_year` | yes | `YYYY-YY`, second part = first + 1 (e.g. `2026-27`) |
| `institution_student_id` | yes | Letters, digits, `/ _ -`, ≤ 64 chars |
| `apaar_id` | yes | Must match the configured format (demo: `DEMO-APAAR-######`). Whitespace removed, upper-cased |
| `full_name` | yes | Letters, spaces, `. ' -` |
| `date_of_birth` | yes | `YYYY-MM-DD`, in the past |
| `gender` | no | `F`, `M` or `O` |
| `admission_date` | yes | `YYYY-MM-DD`, not in the future |
| `seat_type` | yes | `REGULAR` or `SUPERNUMERARY` |
| `nri_category` | yes | `Y`/`N` (also `YES`/`NO`) |
| `oci_status` | yes | `Y`/`N` |
| `foreign_national_status` | yes | `Y`/`N` |
| `nationality` | yes | ISO 3166-1 alpha-2, e.g. `IN` |
| `enrolment_status` | yes | `ENROLLED`, `CANCELLED` or `WITHDRAWN` |

## File-level rejections (nothing is saved)

| Code | Meaning |
|---|---|
| `EMPTY_FILE` / `NO_DATA_ROWS` | No header or no data |
| `NOT_A_CSV` | Binary content |
| `ENCODING_INVALID` | Not UTF-8 |
| `MISSING_COLUMNS` / `DUPLICATE_COLUMNS` | Header problems |
| `TOO_MANY_ROWS` | Over the row limit |
| `MALFORMED_CSV` | Broken quoting |

## Row-level rejections (row not saved; other rows continue)

| Code | Meaning |
|---|---|
| `REQUIRED_FIELD_MISSING`, `IDENTIFIER_MISSING` | Empty required value |
| `IDENTIFIER_FORMAT_INVALID` | APAAR ID does not match the configured format |
| `INVALID_VALUE`, `INVALID_DATE`, `INVALID_ACADEMIC_YEAR`, `VALUE_TOO_LONG`, `ROW_SHAPE_INVALID` | Bad value or row shape |
| `INSTITUTION_MISMATCH` | Row is for another institution |
| `UNKNOWN_PROGRAMME` | Programme not configured |
| `DUPLICATE_IN_FILE` | Same APAAR ID + programme + year earlier in the file (first occurrence wins) |
| `IDENTITY_MISMATCH` | Same APAAR ID with different identity details than an earlier row or the stored record |
| `STUDENT_ID_CONFLICT` | Student ID already used for a different APAAR ID |

Messages never include the submitted identifier. The **error report** CSV lists line, student
ID, field, code and message.

## Matching and idempotency

- Student = (institution, APAAR ID). Admission = (student, programme, academic year).
- A row for an existing admission updates it if any admission field changed (`updated`),
  otherwise it is `unchanged`. Re-uploading the same file therefore changes nothing and is
  flagged as `REPEAT_UPLOAD`.
- Identity details are never overwritten by an upload; change them on the student page, where
  the edit requires a reason and is audited.

## Transaction model

Valid rows, row results, the batch summary and the rule-engine results are written in **one
transaction**. Any unexpected error rolls everything back and records a `failed` batch, so an
upload never leaves partial, unreported data.
