"""CSV upload -> row validation -> persistence -> findings -> dashboard (the core MVP flow)."""

import csv
import io
import re
import uuid

from sqlalchemy import func, select

from app.models import Admission, AuditEvent, Finding, Institution, Student, UploadBatch
from app.seed import CROSS_INSTITUTION_ID, demo_upload_rows
from tests.conftest import ARANYA_OPERATOR, NARMADA_ADMIN

IDENTIFIER = re.compile(r"DEMO-APAAR-\d{6}")


def aranya(db) -> Institution:
    return db.scalar(select(Institution).where(Institution.code == "DEMO-INST-001"))


def upload(c, content: bytes, name: str = "admissions.csv"):
    return c.post("/api/v1/uploads/students", files={"file": (name, content, "text/csv")})


def test_demo_upload_end_to_end(as_user, db):
    c = as_user(ARANYA_OPERATOR)
    sample = c.get("/api/v1/demo/sample-upload.csv")
    assert sample.status_code == 200
    response = upload(c, sample.content)
    assert response.status_code == 201, response.text
    batch = response.json()
    assert batch["status"] == "partial"
    assert batch["rejected_rows"] == 6
    assert batch["created_rows"] == batch["total_rows"] - 6
    assert batch["findings_opened"] == 5  # exactly the planted problems, no false positives

    rows = c.get(
        f"/api/v1/uploads/{batch['id']}/rows", params={"status": "rejected", "page_size": 100}
    ).json()["items"]
    codes = {e["code"] for r in rows for e in r["errors"]}
    assert codes == {
        "IDENTIFIER_MISSING",
        "IDENTIFIER_FORMAT_INVALID",
        "DUPLICATE_IN_FILE",
        "INVALID_DATE",
        "UNKNOWN_PROGRAMME",
        "INVALID_VALUE",
    }

    findings = {
        f.rule_code: f
        for f in db.scalars(
            select(Finding).where(Finding.source_batch_id == uuid.UUID(batch["id"]))
        )
    }
    assert set(findings) == {
        "INTAKE_EXCEEDED",
        "CROSS_INSTITUTION_DUPLICATE",
        "CATEGORY_CONFLICT",
        "MULTIPLE_ACTIVE_ADMISSIONS",
        "AGE_AT_ADMISSION",
    }
    intake = findings["INTAKE_EXCEEDED"].evidence["metrics"]
    assert intake == {"counted": 65, "limit": 60, "excess": 5}

    # The cross-institution match is flagged on BOTH sides, and Aranya cannot see Narmada.
    cross = db.scalars(
        select(Finding).where(Finding.rule_code == "CROSS_INSTITUTION_DUPLICATE")
    ).all()
    assert {f.institution.code for f in cross} == {"DEMO-INST-001", "DEMO-INST-003"}
    # The batch counts and links only the uploading institution's own findings.
    own = db.scalars(select(Finding).where(Finding.source_batch_id == uuid.UUID(batch["id"]))).all()
    assert batch["findings_opened"] == len(own)
    assert {f.institution.code for f in own} == {"DEMO-INST-001"}
    other_side = next(f for f in cross if f.institution.code == "DEMO-INST-003")
    assert other_side.source_batch_id is None
    aranya_cross = next(f for f in cross if f.institution.code == "DEMO-INST-001")
    detail = c.get(f"/api/v1/findings/{aranya_cross.id}").json()
    assert detail["restricted_evidence"] is None and detail["restricted_evidence_hidden"]
    assert "Narmada" not in str(detail)


def test_dashboard_matches_database_counts(as_user, db):
    c = as_user(ARANYA_OPERATOR)
    upload(c, c.get("/api/v1/demo/sample-upload.csv").content)
    dashboard = c.get("/api/v1/dashboard/institution").json()
    year = dashboard["academic_year"]
    expected = db.scalar(
        select(func.count())
        .select_from(Admission)
        .where(
            Admission.institution_id == aranya(db).id,
            Admission.academic_year == year,
            Admission.enrolment_status == "ENROLLED",
        )
    )
    assert dashboard["kpis"]["active_enrolments"] == expected
    cse = next(p for p in dashboard["programmes"] if p["code"] == "BTECH-CSE")
    assert cse["status"] == "exceeded" and cse["regular_enrolled"] == 65
    open_findings = db.scalar(
        select(func.count())
        .select_from(Finding)
        .where(
            Finding.institution_id == aranya(db).id,
            Finding.status.in_(("open", "in_review", "escalated")),
        )
    )
    assert dashboard["kpis"]["open_findings"] == open_findings


def test_repeat_upload_is_idempotent(as_user, db):
    c = as_user(ARANYA_OPERATOR)
    content = c.get("/api/v1/demo/sample-upload.csv").content
    first = upload(c, content).json()
    students_before = db.scalar(select(func.count()).select_from(Student))
    findings_before = db.scalar(select(func.count()).select_from(Finding))

    second = upload(c, content).json()
    assert second["repeat_of_batch_id"] == first["id"]
    assert {w["code"] for w in second["warnings"]} == {"REPEAT_UPLOAD"}
    assert second["created_rows"] == 0 and second["updated_rows"] == 0
    assert second["unchanged_rows"] == first["created_rows"]
    assert second["findings_opened"] == 0
    assert db.scalar(select(func.count()).select_from(Student)) == students_before
    assert db.scalar(select(func.count()).select_from(Finding)) == findings_before


def test_update_through_upload_and_identity_protection(as_user, db):
    c = as_user(ARANYA_OPERATOR)
    content = c.get("/api/v1/demo/sample-upload.csv").content.decode()
    upload(c, content.encode())
    reader = list(csv.reader(io.StringIO(content)))
    header, first = reader[0], reader[1]

    changed = list(first)
    changed[header.index("enrolment_status")] = "WITHDRAWN"
    renamed = list(reader[2])
    renamed[header.index("full_name")] = "Someone Else"
    body = io.StringIO()
    csv.writer(body, lineterminator="\n").writerows([header, changed, renamed])
    batch = upload(c, body.getvalue().encode()).json()
    assert batch["updated_rows"] == 1 and batch["rejected_rows"] == 1
    rows = c.get(f"/api/v1/uploads/{batch['id']}/rows").json()["items"]
    rejected = next(r for r in rows if r["status"] == "rejected")
    assert rejected["errors"][0]["code"] == "IDENTITY_MISMATCH"
    assert "full_name" in rejected["errors"][0]["message"]


def test_malformed_file_is_rejected_without_writes(as_user, db):
    c = as_user(ARANYA_OPERATOR)
    before = db.scalar(select(func.count()).select_from(Admission))
    response = upload(c, b"name,age\nA,1\n")
    assert response.status_code == 201
    batch = response.json()
    assert batch["status"] == "rejected"
    assert batch["file_errors"][0]["code"] == "MISSING_COLUMNS"
    assert db.scalar(select(func.count()).select_from(Admission)) == before


def test_upload_guards(as_user):
    c = as_user(ARANYA_OPERATOR)
    assert upload(c, b"x", name="data.xlsx").status_code == 415
    big = b"a" * (5 * 1024 * 1024 + 10)
    assert upload(c, big).status_code == 413


def test_cannot_submit_rows_for_another_institution(as_user):
    c = as_user(ARANYA_OPERATOR)
    content = c.get("/api/v1/demo/sample-upload.csv").content.decode()
    content = content.replace("DEMO-INST-001", "DEMO-INST-002")
    batch = upload(c, content.encode()).json()
    assert batch["status"] == "rejected"
    rows = c.get(f"/api/v1/uploads/{batch['id']}/rows", params={"page_size": 5}).json()["items"]
    assert {e["code"] for r in rows for e in r["errors"]} >= {"INSTITUTION_MISMATCH"}


def test_error_report_and_audit_never_contain_identifiers(as_user, db):
    c = as_user(ARANYA_OPERATOR)
    batch = upload(c, c.get("/api/v1/demo/sample-upload.csv").content).json()
    report = c.get(f"/api/v1/uploads/{batch['id']}/errors.csv")
    assert report.status_code == 200
    assert "IDENTIFIER_FORMAT_INVALID" in report.text
    assert not IDENTIFIER.search(report.text)
    for event in db.scalars(select(AuditEvent)):
        assert not IDENTIFIER.search(str(event.details))
    batch_row = db.get(UploadBatch, uuid.UUID(batch["id"]))
    assert not IDENTIFIER.search(str(batch_row.file_errors) + str(batch_row.warnings))


def test_central_reviewer_sees_both_sides_of_cross_institution_match(as_user, db):
    operator = as_user(ARANYA_OPERATOR)
    upload(operator, operator.get("/api/v1/demo/sample-upload.csv").content)
    narmada_admin = as_user(NARMADA_ADMIN)
    findings = narmada_admin.get(
        "/api/v1/findings", params={"category": "CROSS_INSTITUTION"}
    ).json()["items"]
    assert len(findings) == 1
    assert CROSS_INSTITUTION_ID not in str(findings)


def test_sample_generator_is_deterministic(db):
    inst = aranya(db)
    assert demo_upload_rows(db, inst) == demo_upload_rows(db, inst)
