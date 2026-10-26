"""Authorised verification (REQ-05, REQ-06).

Two independent answers are given and never merged:

1. Repository check (real): does this platform hold records for the identifier, and has the
   student's consent for third-party verification been recorded? Details are disclosed only
   with consent, and only the minimum needed.
2. Identity provider check (SIMULATED): the mock APAAR adapter. Always labelled simulated.
"""

import hmac
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import Principal, require
from app.core.identifiers import fingerprint, matches_format, normalize_identifier
from app.core.permissions import Permission
from app.db.base import utcnow
from app.db.session import get_db
from app.models import Admission, Institution, Student, User, VerifiableRecord, VerificationAttempt
from app.schemas.common import Page, PageParams
from app.services import audit
from app.services.records import consent_granted, normalize_reference, record_digest
from app.services.settings import load_policy
from app.services.verification.adapter import SIMULATED_LABEL, get_provider

router = APIRouter(prefix="/verification", tags=["verification"])

FORMAT_NOTE = "A format check confirms only the shape of the identifier, not that it is authentic."
CONSENT_NOTE = (
    "Record details are shared only when the student's consent for third-party verification is "
    "on record. Institutions holding records without consent are not named."
)


class IdentifierLookupIn(BaseModel):
    apaar_id: str = Field(min_length=1, max_length=64)
    purpose: str = Field(min_length=5, max_length=160)


class ReferenceLookupIn(BaseModel):
    reference_code: str = Field(min_length=5, max_length=24)
    purpose: str = Field(min_length=5, max_length=160)


class AttemptOut(BaseModel):
    id: uuid.UUID
    kind: str
    purpose: str
    provider: str
    simulated: bool
    outcome: str
    details: dict[str, Any]
    requested_by: str | None
    requester_role: str
    created_at: datetime


def _disclose(admission: Admission, institution: Institution) -> dict[str, Any]:
    return {
        "institution_code": institution.code,
        "institution_name": institution.name,
        "programme": f"{admission.programme.name} ({admission.programme.code})",
        "academic_year": admission.academic_year,
        "enrolment_status": admission.enrolment_status,
        "admission_date": admission.admission_date.isoformat(),
    }


@router.post("/lookup")
def lookup_by_identifier(
    body: IdentifierLookupIn,
    request: Request,
    principal: Principal = Depends(require(Permission.VERIFY_LOOKUP)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    policy = load_policy(db)
    normalized = normalize_identifier(body.apaar_id)
    format_ok = matches_format(normalized, policy.identifier_format.pattern)
    students = (
        db.scalars(
            select(Student)
            .where(Student.apaar_fingerprint == fingerprint(normalized))
            .options(
                selectinload(Student.admissions).selectinload(Admission.programme),
                selectinload(Student.institution),
            )
        ).all()
        if format_ok
        else []
    )

    disclosed: list[dict[str, Any]] = []
    withheld = 0
    for student in students:
        if consent_granted(db, student.id):
            for admission in sorted(
                student.admissions, key=lambda a: a.academic_year, reverse=True
            ):
                disclosed.append(
                    {"student_name": student.full_name, **_disclose(admission, student.institution)}
                )
        else:
            withheld += 1
    if disclosed:
        repository_status = "records_disclosed"
    elif withheld:
        repository_status = "consent_not_on_record"
    else:
        repository_status = "no_records"

    provider = get_provider()
    provider_result = provider.verify(normalized) if format_ok else None
    attempt = VerificationAttempt(
        id=uuid.uuid4(),
        requested_by_id=principal.user_id,
        requester_role=principal.role,
        kind="identifier_lookup",
        purpose=body.purpose,
        student_id=students[0].id if len(students) == 1 else None,
        provider=provider.name,
        simulated=provider.simulated,
        outcome=provider_result.outcome if provider_result else "format_invalid",
        details={
            "repository_status": repository_status,
            "records_disclosed": len(disclosed),
            "institutions_withheld": withheld,
            "message": provider_result.message if provider_result else FORMAT_NOTE,
        },
    )
    db.add(attempt)
    audit.record(
        db,
        action="verification.identifier_lookup",
        principal=principal,
        request=request,
        target_type="verification_attempt",
        target_id=attempt.id,
        details={
            "purpose": body.purpose,
            "repository_status": repository_status,
            "format_ok": format_ok,
            "provider_outcome": attempt.outcome,
        },
    )
    db.commit()
    return {
        "attempt_id": str(attempt.id),
        "checked_at": utcnow().isoformat(),
        "format_check": {
            "passed": format_ok,
            "rule": policy.identifier_format.label,
            "note": FORMAT_NOTE,
        },
        "repository": {
            "status": repository_status,
            "records": disclosed,
            "withheld_count": withheld,
            "note": CONSENT_NOTE,
        },
        "identity_provider": {
            "provider": provider.display_name,
            "simulated": provider_result.simulated,
            "label": SIMULATED_LABEL,
            "outcome": provider_result.outcome,
            "message": provider_result.message,
        }
        if provider_result
        else None,
    }


@router.post("/reference")
def lookup_by_reference(
    body: ReferenceLookupIn,
    request: Request,
    principal: Principal = Depends(require(Permission.VERIFY_LOOKUP)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    code = normalize_reference(body.reference_code)
    record = db.scalar(select(VerifiableRecord).where(VerifiableRecord.reference_code == code))
    details: dict[str, Any] | None = None
    consent = False
    if record is None:
        status = "not_found"
    elif record.revoked_at is not None:
        status = "superseded"
    else:
        admission = record.admission
        intact = hmac.compare_digest(record.digest, record_digest(admission))
        status = "valid" if intact else "changed_since_issue"
        consent = consent_granted(db, admission.student_id)
        if consent:
            institution = db.get(Institution, admission.institution_id)
            assert institution is not None
            details = {
                "student_name": admission.student.full_name,
                "issued_at": record.issued_at.isoformat(),
                **_disclose(admission, institution),
            }

    attempt = VerificationAttempt(
        id=uuid.uuid4(),
        requested_by_id=principal.user_id,
        requester_role=principal.role,
        kind="reference_check",
        purpose=body.purpose,
        student_id=record.admission.student_id if record else None,
        institution_id=record.institution_id if record else None,
        provider="local_repository",
        simulated=False,
        outcome=status,
        details={"consent_on_record": consent, "disclosed": details is not None},
    )
    db.add(attempt)
    audit.record(
        db,
        action="verification.reference_check",
        principal=principal,
        request=request,
        target_type="verification_attempt",
        target_id=attempt.id,
        details={"purpose": body.purpose, "outcome": status},
    )
    db.commit()
    messages = {
        "valid": "This record reference exists and the record is unchanged since it was issued.",
        "changed_since_issue": "This reference exists, but the record has changed since it was "
        "issued. Ask the institution for a current record.",
        "superseded": "This reference was replaced by a newer one. Ask the holder for the "
        "current record.",
        "not_found": "No record with this reference exists on this platform.",
    }
    return {
        "attempt_id": str(attempt.id),
        "checked_at": utcnow().isoformat(),
        "status": status,
        "message": messages[status],
        "consent_on_record": consent,
        "record": details,
        "note": "This checks the platform's own records (synthetic demo data). It is not an "
        "official APAAR or AICTE verification.",
    }


@router.get("/attempts", response_model=Page[AttemptOut])
def list_attempts(
    paging: PageParams = Depends(),
    principal: Principal = Depends(require(Permission.VERIFY_LOOKUP)),
    db: Session = Depends(get_db),
) -> Page[AttemptOut]:
    stmt = select(VerificationAttempt, User).outerjoin(
        User, VerificationAttempt.requested_by_id == User.id
    )
    if principal.role == "authorized_verifier":
        stmt = stmt.where(VerificationAttempt.requested_by_id == principal.user_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(
        stmt.order_by(VerificationAttempt.created_at.desc())
        .offset(paging.offset)
        .limit(paging.page_size)
    ).all()
    return Page(
        items=[
            AttemptOut(
                id=a.id,
                kind=a.kind,
                purpose=a.purpose,
                provider=a.provider,
                simulated=a.simulated,
                outcome=a.outcome,
                details=a.details,
                requested_by=u.full_name if u else None,
                requester_role=a.requester_role,
                created_at=a.created_at,
            )
            for a, u in rows
        ],
        total=total,
        page=paging.page,
        page_size=paging.page_size,
    )
