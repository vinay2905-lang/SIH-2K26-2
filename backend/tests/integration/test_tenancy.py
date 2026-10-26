"""Institution users must never read or change another institution's data."""

import pytest
from sqlalchemy import select

from app.models import Admission, Finding, Institution, Student, UploadBatch
from tests.conftest import ARANYA_ADMIN, ARANYA_OPERATOR, CENTRAL, SYSADMIN, VERIFIER


def kaveri(db) -> Institution:
    return db.scalar(select(Institution).where(Institution.code == "DEMO-INST-002"))


def test_lists_are_scoped_even_if_another_institution_is_requested(as_user, db):
    c = as_user(ARANYA_OPERATOR)
    other = kaveri(db)
    students = c.get(
        "/api/v1/students", params={"institution_id": str(other.id), "page_size": 100}
    ).json()
    assert students["total"] > 0
    assert {s["institution"]["code"] for s in students["items"]} == {"DEMO-INST-001"}
    uploads = c.get("/api/v1/uploads", params={"institution_id": str(other.id)}).json()
    assert {u["institution"]["code"] for u in uploads["items"]} == {"DEMO-INST-001"}
    programmes = c.get("/api/v1/programmes", params={"institution_id": str(other.id)}).json()
    assert {p["institution"]["code"] for p in programmes} == {"DEMO-INST-001"}
    report = c.get("/api/v1/reports/enrolment", params={"institution_id": str(other.id)}).json()
    assert {r["institution_code"] for r in report["rows"]} == {"DEMO-INST-001"}


def test_direct_access_to_other_institution_records_is_not_found(as_user, db):
    c = as_user(ARANYA_ADMIN)
    other = kaveri(db)
    student = db.scalar(select(Student).where(Student.institution_id == other.id))
    admission = db.scalar(select(Admission).where(Admission.institution_id == other.id))
    batch = db.scalar(select(UploadBatch).where(UploadBatch.institution_id == other.id))
    finding = db.scalar(select(Finding).where(Finding.institution_id == other.id))

    assert c.get(f"/api/v1/students/{student.id}").status_code == 404
    assert (
        c.patch(
            f"/api/v1/students/{student.id}", json={"full_name": "Changed", "reason": "attack"}
        ).status_code
        == 404
    )
    assert (
        c.patch(
            f"/api/v1/admissions/{admission.id}",
            json={"enrolment_status": "CANCELLED", "reason": "attack"},
        ).status_code
        == 404
    )
    assert (
        c.post(f"/api/v1/students/{student.id}/consent", json={"status": "withdrawn"}).status_code
        == 404
    )
    assert c.post(f"/api/v1/admissions/{admission.id}/certificate").status_code == 404
    assert c.get(f"/api/v1/uploads/{batch.id}").status_code == 404
    assert c.get(f"/api/v1/uploads/{batch.id}/errors.csv").status_code == 404
    assert c.get(f"/api/v1/findings/{finding.id}").status_code == 404
    assert (
        c.post(
            f"/api/v1/findings/{finding.id}/actions",
            json={"action": "comment", "comment": "attack"},
        ).status_code
        == 404
    )

    db.expire_all()
    assert db.get(Student, student.id).full_name != "Changed"
    assert db.get(Admission, admission.id).enrolment_status != "CANCELLED"


def test_lookup_by_identifier_is_scoped(as_user):
    c = as_user(ARANYA_OPERATOR)
    # This identifier belongs to a Kaveri student in the seed.
    assert c.post("/api/v1/students/lookup", json={"apaar_id": "DEMO-APAAR-200001"}).json() == []
    assert (
        len(c.post("/api/v1/students/lookup", json={"apaar_id": "demo-apaar-100001"}).json()) == 1
    )


@pytest.mark.parametrize(
    ("email", "method", "path"),
    [
        (ARANYA_OPERATOR, "get", "/api/v1/dashboard/central"),
        (ARANYA_OPERATOR, "get", "/api/v1/institutions"),
        (ARANYA_OPERATOR, "get", "/api/v1/audit-events"),
        (ARANYA_OPERATOR, "get", "/api/v1/settings"),
        (ARANYA_OPERATOR, "post", "/api/v1/verification/lookup"),
        (ARANYA_ADMIN, "get", "/api/v1/dashboard/central"),
        (VERIFIER, "get", "/api/v1/students"),
        (VERIFIER, "get", "/api/v1/findings"),
        (VERIFIER, "get", "/api/v1/dashboard/institution"),
        (SYSADMIN, "get", "/api/v1/students"),
        (SYSADMIN, "get", "/api/v1/findings"),
        (CENTRAL, "get", "/api/v1/settings"),
        (CENTRAL, "get", "/api/v1/dashboard/institution"),
    ],
)
def test_role_permissions_are_enforced_server_side(as_user, email, method, path):
    c = as_user(email)
    kwargs = (
        {"json": {"apaar_id": "DEMO-APAAR-000001", "purpose": "testing"}}
        if method == "post"
        else {}
    )
    response = getattr(c, method)(path, **kwargs)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_denied_access_is_audited(as_user, db):
    c = as_user(VERIFIER)
    c.get("/api/v1/students")
    from app.models import AuditEvent

    event = db.scalar(select(AuditEvent).where(AuditEvent.action == "access.denied"))
    assert event is not None and event.details["permission"] == "students.read"


def test_central_reviewer_sees_all_institutions(as_user):
    c = as_user(CENTRAL)
    codes = {
        s["institution"]["code"]
        for s in c.get("/api/v1/students", params={"page_size": 100}).json()["items"]
    }
    assert len(c.get("/api/v1/institutions").json()) == 4
    assert codes  # at least one institution visible; paging limits how many appear
