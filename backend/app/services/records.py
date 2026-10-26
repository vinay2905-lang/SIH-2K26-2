"""Verifiable record references for certificates (REQ-06, REQ-10).

A record reference is issued for one admission. Its digest is a keyed HMAC over the record's
key fields, so a verifier can tell whether the record changed after issue. This is a prototype
integrity check: it is not proof of identity and not an official credential.
"""

import hashlib
import hmac
import json
import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import utcnow
from app.models import Admission, ConsentRecord, VerifiableRecord

CONSENT_PURPOSE = "third_party_verification"
_REFERENCE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O or 1/I


def record_digest(admission: Admission) -> str:
    student = admission.student
    payload = json.dumps(
        {
            "admission": str(admission.id),
            "student": student.apaar_fingerprint,
            "institution": str(admission.institution_id),
            "programme": admission.programme.code,
            "academic_year": admission.academic_year,
            "status": admission.enrolment_status,
            "student_id": student.institution_student_id,
            "name": student.full_name,
            "dob": student.date_of_birth.isoformat(),
        },
        sort_keys=True,
    )
    key = get_settings().identifier_hmac_key.encode()
    return hmac.new(key, b"record-digest:" + payload.encode(), hashlib.sha256).hexdigest()


def new_reference_code() -> str:
    groups = ["".join(secrets.choice(_REFERENCE_ALPHABET) for _ in range(4)) for _ in range(3)]
    return "VR-" + "-".join(groups)


def normalize_reference(code: str) -> str:
    return code.strip().upper()


def issue_record(
    db: Session, admission: Admission, issued_by_id: uuid.UUID | None
) -> tuple[VerifiableRecord, bool]:
    """Reuse the current reference if the record is unchanged; otherwise revoke and reissue.
    Returns (record, newly_issued)."""
    digest = record_digest(admission)
    current = db.scalar(
        select(VerifiableRecord)
        .where(VerifiableRecord.admission_id == admission.id)
        .where(VerifiableRecord.revoked_at.is_(None))
        .order_by(VerifiableRecord.issued_at.desc())
    )
    if current is not None and hmac.compare_digest(current.digest, digest):
        return current, False
    if current is not None:
        current.revoked_at = utcnow()
    record = VerifiableRecord(
        admission_id=admission.id,
        institution_id=admission.institution_id,
        reference_code=new_reference_code(),
        digest=digest,
        issued_by_id=issued_by_id,
    )
    db.add(record)
    db.flush()
    return record, True


def current_consent(db: Session, student_id: uuid.UUID) -> ConsentRecord | None:
    return db.scalar(
        select(ConsentRecord)
        .where(ConsentRecord.student_id == student_id)
        .where(ConsentRecord.purpose == CONSENT_PURPOSE)
        .order_by(ConsentRecord.created_at.desc())
        .limit(1)
    )


def consent_granted(db: Session, student_id: uuid.UUID) -> bool:
    consent = current_consent(db, student_id)
    return consent is not None and consent.status == "granted"
