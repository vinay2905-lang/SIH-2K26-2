# Demo script (≈ 8 minutes)

Uses only synthetic data. Password for every demo account: `Demo@12345` (local demo only).
The login page lists the accounts — click one to fill the form.

## Before you start

```bash
# Reset to a clean, known state (wipes ALL data, then loads demo data)
cd backend && python -m app.seed --reset
```

Open `http://localhost:8000` (Docker or built frontend) or `http://localhost:5173` (dev).

## 1. Institution submits data — `aranya.operator@demo.example`

1. **Dashboard** shows “No admissions submitted for 2026-27 yet” and last year's upload.
2. **Uploads → Demo sample file** downloads a 171-row CSV with deliberately planted problems.
3. Drop it on the upload area → **Upload and validate**.
4. The batch page shows *Partially accepted*: 165 accepted, 6 rejected, 5 new findings.
   - **Rejected** tab: missing APAAR ID, malformed ID, duplicate row, bad date, unknown
     programme, invalid seat type — each with field, reason and code.
   - **Download error report** — note it contains no APAAR IDs.
5. **Dashboard** now shows B.Tech CSE at 108 % (*Over intake*) and the open findings.
6. Optional: **Uploads** → upload the same file again → *REPEAT_UPLOAD*, 0 created, 0 new findings
   (idempotent).

## 2. Explainable review — `aranya.admin@demo.example`

1. **Exception queue**: highest severity first; every row states its reason.
2. Open **Conflicting NRI / OCI / FN / nationality fields**: evidence table, *what it checks*,
   *why it matters*, the **configurable policy assumption**, recommended action, history.
3. Add a comment → **Resolve**. History and audit trail update.
4. Open **Admissions exceed approved intake** — *Resolve* is not offered (central decision).
   Comment → **Escalate to central review**.
5. Open the student **Tanvi Rao** → *Record* → printable admission record with APAAR ID
   alongside the institution student ID and a record reference (copy the `VR-…` code).
6. **Audit trail** shows sign-in, upload, review and certificate events.

## 3. Central monitoring — `central.reviewer@demo.example`

1. **Central monitoring**: institutions reporting (3 / 4 — Brahmaputra has not reported),
   enrolments, utilisation, open and escalated findings, cross-institution matches,
   upload-quality chart.
2. **Exception queue → Escalated**: resolve Aranya's intake finding with a comment.
3. Filter **Cross-institution match**: the evidence section *visible to central reviewers only*
   names both institutions; institution users only see “1 other institution”.
4. **Reports** → download the enrolment CSV (period, scope, definitions included; export audited).

## 4. Consent-based verification — `verifier@demo.example`

1. Banner states **SIMULATED — NOT OFFICIAL APAAR VERIFICATION**.
2. APAAR ID `DEMO-APAAR-210001`, purpose “Pre-employment background check” → **Verify**:
   - *Platform record check*: record found, consent on record, minimum details.
   - *APAAR identity provider*: clearly simulated result, shown separately.
3. `DEMO-APAAR-210002` → record exists but **no consent on record** → details withheld.
4. **By record reference** → paste the `VR-…` code from step 2.5 → *Valid* (unchanged since issue).
5. Mock provider outcomes are deterministic by the last digit: 0–6 match, 7 no match,
   8 provider unavailable, 9 pending.

## 5. Configurable policy — `sysadmin@demo.example`

Show the identifier-format presets, counted statuses, thresholds and rule switches; explain
that these are assumptions pending authoritative rules and that saving re-validates everything.

## What is real vs simulated

| Real in this prototype | Simulated / synthetic |
|---|---|
| Upload, validation, findings, review workflow, dashboards, reports, audit, consent gating, record references, RBAC and isolation | APAAR identity provider (mock adapter), all institutions, students, identifiers and intake figures |

## Backup plan

- Keep a screen recording of this script.
- If the network is unavailable, everything still runs locally (no external calls).
- `python -m app.seed --reset` restores the starting state in a few seconds.
