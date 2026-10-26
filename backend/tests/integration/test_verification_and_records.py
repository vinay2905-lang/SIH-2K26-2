"""Consent-gated verification, simulated provider labelling, record references."""

from sqlalchemy import select

from app.models import Admission, ConsentRecord, Institution, Student, VerificationAttempt
from app.services.records import CONSENT_PURPOSE, consent_granted
from app.services.verification.adapter import SIMULATED_LABEL
from tests.conftest import ARANYA_OPERATOR, CENTRAL, KAVERI_ADMIN, KAVERI_OPERATOR, VERIFIER


def kaveri_student(db, *, consent: bool) -> Student:
    inst = db.scalar(select(Institution).where(Institution.code == "DEMO-INST-002"))
    for student in db.scalars(
        select(Student)
        .where(Student.institution_id == inst.id)
        .order_by(Student.institution_student_id)
    ):
        if consent_granted(db, student.id) is consent:
            return student
    raise AssertionError("no matching student in seed")


def identifier_of(student: Student) -> str:
    from app.core.identifiers import decrypt_identifier

    return decrypt_identifier(student.apaar_ciphertext)


def lookup(c, apaar_id: str):
    return c.post(
        "/api/v1/verification/lookup",
        json={"apaar_id": apaar_id, "purpose": "Employment background check"},
    )


def test_lookup_with_consent_discloses_minimum_record(as_user, db):
    student = kaveri_student(db, consent=True)
    body = lookup(as_user(VERIFIER), identifier_of(student)).json()
    assert body["format_check"]["passed"] is True
    assert body["repository"]["status"] == "records_disclosed"
    record = body["repository"]["records"][0]
    assert set(record) == {
        "student_name",
        "institution_code",
        "institution_name",
        "programme",
        "academic_year",
        "enrolment_status",
        "admission_date",
    }
    provider = body["identity_provider"]
    assert provider["simulated"] is True and provider["label"] == SIMULATED_LABEL
    assert provider["message"].startswith(SIMULATED_LABEL)


def test_lookup_without_consent_withholds_details(as_user, db):
    student = kaveri_student(db, consent=False)
    body = lookup(as_user(VERIFIER), identifier_of(student)).json()
    assert body["repository"]["status"] == "consent_not_on_record"
    assert body["repository"]["records"] == []
    assert "Kaveri" not in str(body["repository"])


def test_invalid_format_skips_provider_and_unknown_id_has_no_records(as_user):
    verifier = as_user(VERIFIER)
    bad = lookup(verifier, "not-an-id").json()
    assert bad["format_check"]["passed"] is False and bad["identity_provider"] is None
    unknown = lookup(verifier, "DEMO-APAAR-999990").json()
    assert unknown["repository"]["status"] == "no_records"


def test_attempts_are_logged_without_raw_identifier(as_user, db):
    student = kaveri_student(db, consent=True)
    identifier = identifier_of(student)
    lookup(as_user(VERIFIER), identifier)
    attempt = db.scalars(select(VerificationAttempt)).one()
    assert attempt.simulated is True and attempt.purpose == "Employment background check"
    assert identifier not in str(attempt.details)
    history = as_user(VERIFIER).get("/api/v1/verification/attempts").json()
    assert history["total"] == 1


def test_withdrawing_consent_stops_disclosure(as_user, db):
    student = kaveri_student(db, consent=True)
    operator = as_user(KAVERI_OPERATOR)
    response = operator.post(
        f"/api/v1/students/{student.id}/consent",
        json={"status": "withdrawn", "note": "Student request"},
    )
    assert response.status_code == 200
    assert response.json()["consent"]["status"] == "withdrawn"
    body = lookup(as_user(VERIFIER), identifier_of(student)).json()
    assert body["repository"]["status"] == "consent_not_on_record"
    history = db.scalars(
        select(ConsentRecord).where(
            ConsentRecord.student_id == student.id, ConsentRecord.purpose == CONSENT_PURPOSE
        )
    ).all()
    assert len(history) >= 2  # append-only


def test_certificate_and_reference_check(as_user, db):
    student = kaveri_student(db, consent=True)
    admission = db.scalars(select(Admission).where(Admission.student_id == student.id)).first()
    admin = as_user(KAVERI_ADMIN)
    certificate = admin.post(f"/api/v1/admissions/{admission.id}/certificate").json()
    assert certificate["student"]["apaar_id"] == identifier_of(student)
    assert certificate["reference_code"].startswith("VR-")
    again = admin.post(f"/api/v1/admissions/{admission.id}/certificate").json()
    assert again["reference_code"] == certificate["reference_code"]
    assert again["newly_issued"] is False

    verifier = as_user(VERIFIER)
    check = verifier.post(
        "/api/v1/verification/reference",
        json={
            "reference_code": certificate["reference_code"].lower(),
            "purpose": "Offer letter check",
        },
    )
    assert check.json()["status"] == "valid"
    assert check.json()["record"]["student_name"] == student.full_name

    admin.patch(
        f"/api/v1/admissions/{admission.id}",
        json={"enrolment_status": "WITHDRAWN", "reason": "Left the programme"},
    )
    changed = verifier.post(
        "/api/v1/verification/reference",
        json={"reference_code": certificate["reference_code"], "purpose": "Offer letter check"},
    )
    assert changed.json()["status"] == "changed_since_issue"

    reissued = admin.post(f"/api/v1/admissions/{admission.id}/certificate").json()
    assert reissued["reference_code"] != certificate["reference_code"]
    superseded = verifier.post(
        "/api/v1/verification/reference",
        json={"reference_code": certificate["reference_code"], "purpose": "Offer letter check"},
    )
    assert superseded.json()["status"] == "superseded"
    missing = verifier.post(
        "/api/v1/verification/reference",
        json={"reference_code": "VR-AAAA-BBBB-CCCC", "purpose": "Offer letter check"},
    )
    assert missing.json()["status"] == "not_found"


def test_certificate_requires_institution_admin(as_user, db):
    student = kaveri_student(db, consent=True)
    admission = db.scalars(select(Admission).where(Admission.student_id == student.id)).first()
    assert (
        as_user(KAVERI_OPERATOR).post(f"/api/v1/admissions/{admission.id}/certificate").status_code
        == 403
    )
    assert (
        as_user(CENTRAL).post(f"/api/v1/admissions/{admission.id}/certificate").status_code == 403
    )


def test_institution_identity_check_is_simulated(as_user, db):
    inst = db.scalar(select(Institution).where(Institution.code == "DEMO-INST-001"))
    student = db.scalar(select(Student).where(Student.institution_id == inst.id))
    response = as_user(ARANYA_OPERATOR).post(f"/api/v1/students/{student.id}/identity-check")
    assert response.status_code == 200
    body = response.json()
    assert body["simulated"] is True and body["provider"] == "mock_apaar"
    assert body["message"].startswith(SIMULATED_LABEL)


def test_student_detail_masks_identifier(as_user, db):
    inst = db.scalar(select(Institution).where(Institution.code == "DEMO-INST-001"))
    student = db.scalar(select(Student).where(Student.institution_id == inst.id))
    body = as_user(ARANYA_OPERATOR).get(f"/api/v1/students/{student.id}").json()
    assert body["apaar_masked"].startswith("••••••••")
    assert identifier_of(student) not in str(body)
    listing = as_user(ARANYA_OPERATOR).get("/api/v1/students").json()
    assert "DEMO-APAAR-" not in str(listing)
