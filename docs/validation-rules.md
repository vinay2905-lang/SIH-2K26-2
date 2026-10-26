# Validation rules

Two layers, kept separate on purpose:

1. **Row validation** (deterministic, blocking) — runs before anything is saved. A failing row
   is rejected with a code, field and reason. See [csv-import.md](csv-import.md).
2. **Findings** (deterministic, non-blocking) — run on saved records after every upload or
   edit. A finding is a **review signal**, never a verdict of fraud or misconduct. Every finding
   records which rule fired, the facts compared (identifiers masked), why it matters and what a
   reviewer can do.

No machine-learning or anomaly scoring is used for compliance checks.

## Finding rules

| Code | Category | Severity | Fires when | Resolved by | Assumption |
|---|---|---|---|---|---|
| `INTAKE_EXCEEDED` | Intake | high | Counted regular-seat admissions for a programme-year exceed approved intake | Central | A3, A4 |
| `SUPERNUMERARY_EXCEEDED` | Intake | high | Counted supernumerary-seat admissions exceed configured supernumerary seats | Central | A3, A4 |
| `INTAKE_NOT_CONFIGURED` | Intake | high | Admissions exist for a programme-year with no approved intake | Central | — |
| `MULTIPLE_ACTIVE_ADMISSIONS` | Duplicate | medium | A student has 2+ counted admissions in one year at the same institution | Institution | — |
| `CROSS_INSTITUTION_DUPLICATE` | Cross-institution | high | The same APAAR ID (keyed fingerprint) has counted admissions at 2+ institutions in one year. Raised for each institution; only central reviewers see which institutions | Central | A9 |
| `CATEGORY_CONFLICT` | Consistency | medium | NRI + FN, NRI + OCI, FN with nationality IN, OCI with nationality IN, or NRI with non-IN nationality | Institution | A5 |
| `AGE_AT_ADMISSION` | Consistency | low | Age on admission date outside the configured range | Institution | A6 |
| `ADMISSION_DATE_OUTSIDE_YEAR` | Consistency | low | Admission date outside the configured academic-year window | Institution | A7 |

Assumption codes refer to [assumptions-and-open-questions.md](assumptions-and-open-questions.md).

## Finding lifecycle

```text
open ──start_review──► in_review ──resolve/dismiss──► resolved / dismissed
  │                       │
  └──────escalate─────────┴──► escalated ──(central) resolve/dismiss──►
resolved / dismissed ──reopen──► open
```

- Every action except *start review* needs a comment; all actions go to the finding history
  and the audit trail.
- **Re-validation** runs after each upload, edit, intake change or policy change:
  - an active finding whose condition still holds keeps its status (evidence refreshed if changed);
  - an active finding whose condition is gone is **auto-resolved** by the system with an
    explanation in its history;
  - a condition a reviewer already resolved or dismissed is **not** raised again unless its
    evidence changes (e.g. intake overrun grows from 3 to 5);
  - findings of rules switched off are left untouched.
- Deduplication uses a stable key per rule and subject (e.g. programme + year, admission, or
  student + year).

## Explainability contract

Each finding answers: what was flagged (reason sentence), which rule fired (code + "what it
checks"), what was compared (evidence facts), why it matters (rationale), which policy
assumption applies, what to do (recommended action), and what has happened so far (history).
