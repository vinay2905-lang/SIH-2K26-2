import uuid
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import Principal, require, scoped_institution_id
from app.core.errors import AppError, not_found
from app.core.identifiers import decrypt_identifier, fingerprint, mask, normalize_identifier
from app.core.permissions import Permission
from app.db.session import get_db
from app.models import (
    Admission,
    ConsentRecord,
    Finding,
    Institution,
    Programme,
    Student,
    VerifiableRecord,
    VerificationAttempt,
)
from app.models.finding import ACTIVE_STATUSES
from app.schemas.common import InstitutionRef, Page, PageParams, ProgrammeRef
from app.services import audit
from app.services.ingestion.importer import RecordImporter
from app.services.ingestion.schema import IDENTITY_FIELDS, validate_partial
from app.services.records import CONSENT_PURPOSE, current_consent, issue_record
from app.services.settings import load_policy
from app.services.validation.engine import run_validation
from app.services.verification.adapter import get_provider

router = APIRouter(tags=["students"])


# --- Schemas ------------------------------------------------------------------------------


class AdmissionSummary(BaseModel):
    programme_code: str
    programme_name: str
    academic_year: str
    enrolment_status: str
    seat_type: str


class StudentListItem(BaseModel):
    id: uuid.UUID
    institution_student_id: str
    full_name: str
    apaar_masked: str
    institution: InstitutionRef
    latest_admission: AdmissionSummary | None
    open_findings: int
    consent_status: str | None
    updated_at: datetime


class IssuedRecordOut(BaseModel):
    reference_code: str
    issued_at: datetime


class AdmissionOut(BaseModel):
    id: uuid.UUID
    programme: ProgrammeRef
    academic_year: str
    admission_date: date
    seat_type: str
    nri_category: bool
    oci_status: bool
    foreign_national_status: bool
    enrolment_status: str
    created_at: datetime
    updated_at: datetime
    issued_record: IssuedRecordOut | None


class ConsentOut(BaseModel):
    status: str
    purpose: str
    method: str
    note: str | None
    created_at: datetime


class VerificationOut(BaseModel):
    id: uuid.UUID
    kind: str
    provider: str
    simulated: bool
    outcome: str
    message: str | None
    created_at: datetime


class FindingBrief(BaseModel):
    id: uuid.UUID
    rule_code: str
    title: str
    severity: str
    status: str
    academic_year: str | None
    created_at: datetime


class StudentDetail(BaseModel):
    id: uuid.UUID
    institution_student_id: str
    full_name: str
    date_of_birth: date
    gender: str | None
    nationality: str
    apaar_masked: str
    institution: InstitutionRef
    admissions: list[AdmissionOut]
    consent: ConsentOut | None
    consent_history: list[ConsentOut]
    verifications: list[VerificationOut]
    findings: list[FindingBrief]
    created_at: datetime
    updated_at: datetime


class StudentCreate(BaseModel):
    programme_code: str = Field(max_length=32)
    academic_year: str = Field(max_length=7)
    institution_student_id: str = Field(max_length=64)
    apaar_id: str = Field(max_length=64)
    full_name: str = Field(max_length=160)
    date_of_birth: str = Field(max_length=10)
    gender: str | None = Field(default=None, max_length=1)
    admission_date: str = Field(max_length=10)
    seat_type: str = Field(max_length=16)
    nri_category: bool = False
    oci_status: bool = False
    foreign_national_status: bool = False
    nationality: str = Field(max_length=2)
    enrolment_status: str = Field(max_length=16)


class SubmitResult(BaseModel):
    status: str
    student_id: uuid.UUID
    admission_id: uuid.UUID
    changed_fields: list[str]


class StudentUpdate(BaseModel):
    institution_student_id: str | None = Field(default=None, max_length=64)
    full_name: str | None = Field(default=None, max_length=160)
    date_of_birth: str | None = Field(default=None, max_length=10)
    gender: str | None = Field(default=None, max_length=1)
    nationality: str | None = Field(default=None, max_length=2)
    reason: str = Field(min_length=3, max_length=300)


class AdmissionUpdate(BaseModel):
    admission_date: str | None = Field(default=None, max_length=10)
    seat_type: str | None = Field(default=None, max_length=16)
    nri_category: bool | None = None
    oci_status: bool | None = None
    foreign_national_status: bool | None = None
    enrolment_status: str | None = Field(default=None, max_length=16)
    reason: str = Field(min_length=3, max_length=300)


class LookupRequest(BaseModel):
    apaar_id: str = Field(min_length=1, max_length=64)


class LookupMatch(BaseModel):
    id: uuid.UUID
    institution: InstitutionRef
    institution_student_id: str
    full_name: str


class ConsentUpdate(BaseModel):
    status: Literal["granted", "withdrawn"]
    note: str | None = Field(default=None, max_length=300)


# --- Helpers ------------------------------------------------------------------------------


def _get_student(db: Session, principal: Principal, student_id: uuid.UUID) -> Student:
    student = db.get(Student, student_id)
    if student is None:
        raise not_found("Student")
    principal.ensure_institution(student.institution_id, "Student")
    return student


def _consent_out(c: ConsentRecord) -> ConsentOut:
    return ConsentOut(
        status=c.status, purpose=c.purpose, method=c.method, note=c.note, created_at=c.created_at
    )


def _verification_out(v: VerificationAttempt) -> VerificationOut:
    return VerificationOut(
        id=v.id,
        kind=v.kind,
        provider=v.provider,
        simulated=v.simulated,
        outcome=v.outcome,
        message=v.details.get("message"),
        created_at=v.created_at,
    )


def _student_detail(db: Session, student: Student) -> StudentDetail:
    admissions = db.scalars(
        select(Admission)
        .where(Admission.student_id == student.id)
        .options(selectinload(Admission.programme))
        .order_by(Admission.academic_year.desc())
    ).all()
    issued = {}
    if admissions:
        for record in db.scalars(
            select(VerifiableRecord)
            .where(VerifiableRecord.admission_id.in_([a.id for a in admissions]))
            .where(VerifiableRecord.revoked_at.is_(None))
            .order_by(VerifiableRecord.issued_at)
        ):
            issued[record.admission_id] = record
    consents = db.scalars(
        select(ConsentRecord)
        .where(ConsentRecord.student_id == student.id)
        .where(ConsentRecord.purpose == CONSENT_PURPOSE)
        .order_by(ConsentRecord.created_at.desc())
    ).all()
    verifications = db.scalars(
        select(VerificationAttempt)
        .where(VerificationAttempt.student_id == student.id)
        .order_by(VerificationAttempt.created_at.desc())
        .limit(10)
    ).all()
    findings = db.scalars(
        select(Finding)
        .where(Finding.student_id == student.id)
        .order_by(Finding.created_at.desc())
        .limit(25)
    ).all()
    return StudentDetail(
        id=student.id,
        institution_student_id=student.institution_student_id,
        full_name=student.full_name,
        date_of_birth=student.date_of_birth,
        gender=student.gender,
        nationality=student.nationality,
        apaar_masked=mask(student.apaar_last4),
        institution=InstitutionRef.model_validate(student.institution),
        admissions=[
            AdmissionOut(
                id=a.id,
                programme=ProgrammeRef.model_validate(a.programme),
                academic_year=a.academic_year,
                admission_date=a.admission_date,
                seat_type=a.seat_type,
                nri_category=a.nri_category,
                oci_status=a.oci_status,
                foreign_national_status=a.foreign_national_status,
                enrolment_status=a.enrolment_status,
                created_at=a.created_at,
                updated_at=a.updated_at,
                issued_record=(
                    IssuedRecordOut(
                        reference_code=issued[a.id].reference_code, issued_at=issued[a.id].issued_at
                    )
                    if a.id in issued
                    else None
                ),
            )
            for a in admissions
        ],
        consent=_consent_out(consents[0]) if consents else None,
        consent_history=[_consent_out(c) for c in consents],
        verifications=[_verification_out(v) for v in verifications],
        findings=[
            FindingBrief(
                id=f.id,
                rule_code=f.rule_code,
                title=f.title,
                severity=f.severity,
                status=f.status,
                academic_year=f.academic_year,
                created_at=f.created_at,
            )
            for f in findings
        ],
        created_at=student.created_at,
        updated_at=student.updated_at,
    )


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# --- Routes -------------------------------------------------------------------------------


@router.get("/students", response_model=Page[StudentListItem])
def list_students(
    q: str | None = Query(None, max_length=100),
    institution_id: uuid.UUID | None = None,
    programme_id: uuid.UUID | None = None,
    academic_year: str | None = Query(None, max_length=7),
    enrolment_status: str | None = Query(None, max_length=16),
    has_open_findings: bool | None = None,
    paging: PageParams = Depends(),
    principal: Principal = Depends(require(Permission.STUDENTS_READ)),
    db: Session = Depends(get_db),
) -> Page[StudentListItem]:
    stmt = select(Student)
    scoped = scoped_institution_id(principal, institution_id)
    if scoped is not None:
        stmt = stmt.where(Student.institution_id == scoped)
    if q and q.strip():
        pattern = f"%{_escape_like(q.strip())}%"
        stmt = stmt.where(
            or_(
                Student.full_name.ilike(pattern, escape="\\"),
                Student.institution_student_id.ilike(pattern, escape="\\"),
            )
        )
    admission_filters = []
    if programme_id:
        admission_filters.append(Admission.programme_id == programme_id)
    if academic_year:
        admission_filters.append(Admission.academic_year == academic_year)
    if enrolment_status:
        admission_filters.append(Admission.enrolment_status == enrolment_status.upper())
    if admission_filters:
        stmt = stmt.where(exists().where(Admission.student_id == Student.id, *admission_filters))
    if has_open_findings is not None:
        open_exists = exists().where(
            Finding.student_id == Student.id, Finding.status.in_(ACTIVE_STATUSES)
        )
        stmt = stmt.where(open_exists if has_open_findings else ~open_exists)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    students = db.scalars(
        stmt.options(
            selectinload(Student.institution),
            selectinload(Student.admissions).selectinload(Admission.programme),
        )
        .order_by(Student.updated_at.desc(), Student.institution_student_id)
        .offset(paging.offset)
        .limit(paging.page_size)
    ).all()
    ids = [s.id for s in students]
    open_counts: dict[uuid.UUID, int] = {}
    consents: dict[uuid.UUID, str] = {}
    if ids:
        open_counts = dict(
            db.execute(
                select(Finding.student_id, func.count())
                .where(Finding.student_id.in_(ids), Finding.status.in_(ACTIVE_STATUSES))
                .group_by(Finding.student_id)
            ).all()
        )
        for record in db.scalars(
            select(ConsentRecord)
            .where(ConsentRecord.student_id.in_(ids), ConsentRecord.purpose == CONSENT_PURPOSE)
            .order_by(ConsentRecord.created_at)
        ):
            consents[record.student_id] = record.status

    items = []
    for s in students:
        latest = max(s.admissions, key=lambda a: (a.academic_year, a.updated_at), default=None)
        items.append(
            StudentListItem(
                id=s.id,
                institution_student_id=s.institution_student_id,
                full_name=s.full_name,
                apaar_masked=mask(s.apaar_last4),
                institution=InstitutionRef.model_validate(s.institution),
                latest_admission=AdmissionSummary(
                    programme_code=latest.programme.code,
                    programme_name=latest.programme.name,
                    academic_year=latest.academic_year,
                    enrolment_status=latest.enrolment_status,
                    seat_type=latest.seat_type,
                )
                if latest
                else None,
                open_findings=open_counts.get(s.id, 0),
                consent_status=consents.get(s.id),
                updated_at=s.updated_at,
            )
        )
    return Page(items=items, total=total, page=paging.page, page_size=paging.page_size)


@router.post("/students/lookup", response_model=list[LookupMatch])
def lookup_student(
    body: LookupRequest,
    request: Request,
    principal: Principal = Depends(require(Permission.STUDENTS_READ)),
    db: Session = Depends(get_db),
) -> list[LookupMatch]:
    """Find a record by full APAAR ID. A POST so the identifier never appears in a URL."""
    stmt = select(Student).where(
        Student.apaar_fingerprint == fingerprint(normalize_identifier(body.apaar_id))
    )
    if principal.institution_scoped:
        stmt = stmt.where(Student.institution_id == principal.institution_id)
    matches = db.scalars(stmt.options(selectinload(Student.institution))).all()
    audit.record(
        db,
        action="student.lookup",
        principal=principal,
        request=request,
        details={"matches": len(matches)},
    )
    db.commit()
    return [
        LookupMatch(
            id=s.id,
            institution=InstitutionRef.model_validate(s.institution),
            institution_student_id=s.institution_student_id,
            full_name=s.full_name,
        )
        for s in matches
    ]


@router.post("/students", response_model=SubmitResult, status_code=201)
def submit_student_record(
    body: StudentCreate,
    request: Request,
    principal: Principal = Depends(require(Permission.STUDENTS_WRITE)),
    db: Session = Depends(get_db),
) -> SubmitResult:
    if principal.institution_id is None:
        raise AppError(403, "forbidden", "Only institution users can submit student records")
    institution = db.get(Institution, principal.institution_id)
    assert institution is not None
    policy = load_policy(db)
    importer = RecordImporter(
        db,
        institution,
        actor_id=principal.user_id,
        batch_id=None,
        identifier_pattern=policy.identifier_format.pattern,
        identifier_label=policy.identifier_format.label,
        today=date.today(),
    )
    raw = body.model_dump()
    raw["institution_code"] = institution.code
    for flag in ("nri_category", "oci_status", "foreign_national_status"):
        raw[flag] = "Y" if raw[flag] else "N"
    result = importer.apply(raw)
    if result.status == "rejected":
        db.rollback()
        raise AppError(
            422,
            "record_rejected",
            "The record could not be saved",
            [e.as_dict() for e in result.errors],
        )
    assert result.student is not None and result.admission is not None
    run_validation(db, [institution.id], policy=policy)
    audit.record(
        db,
        action="student.record_submitted",
        principal=principal,
        request=request,
        target_type="student",
        target_id=result.student.id,
        details={
            "result": result.status,
            "programme": body.programme_code,
            "academic_year": body.academic_year,
            "changed_fields": result.changed_fields,
        },
    )
    db.commit()
    return SubmitResult(
        status=result.status,
        student_id=result.student.id,
        admission_id=result.admission.id,
        changed_fields=result.changed_fields,
    )


@router.get("/students/{student_id}", response_model=StudentDetail)
def get_student(
    student_id: uuid.UUID,
    principal: Principal = Depends(require(Permission.STUDENTS_READ)),
    db: Session = Depends(get_db),
) -> StudentDetail:
    return _student_detail(db, _get_student(db, principal, student_id))


@router.patch("/students/{student_id}", response_model=StudentDetail)
def update_student(
    student_id: uuid.UUID,
    body: StudentUpdate,
    request: Request,
    principal: Principal = Depends(require(Permission.STUDENTS_WRITE)),
    db: Session = Depends(get_db),
) -> StudentDetail:
    student = _get_student(db, principal, student_id)
    provided = body.model_dump(exclude_unset=True, exclude={"reason"})
    clean, errors = validate_partial(provided, today=date.today())
    if errors:
        raise AppError(
            422, "validation_error", "Some fields are invalid", [e.as_dict() for e in errors]
        )
    changed = [k for k, v in clean.items() if k in IDENTITY_FIELDS and getattr(student, k) != v]
    if "institution_student_id" in changed:
        clash = db.scalar(
            select(Student.id).where(
                Student.institution_id == student.institution_id,
                Student.institution_student_id == clean["institution_student_id"],
                Student.id != student.id,
            )
        )
        if clash:
            raise AppError(409, "conflict", "That student ID is already used by another record")
    for key in changed:
        setattr(student, key, clean[key])
    if changed:
        student.updated_by_id = principal.user_id
        db.flush()
        run_validation(db, [student.institution_id])
    audit.record(
        db,
        action="student.updated",
        principal=principal,
        request=request,
        target_type="student",
        target_id=student.id,
        details={"changed_fields": changed, "reason": body.reason},
    )
    db.commit()
    return _student_detail(db, student)


@router.patch("/admissions/{admission_id}", response_model=StudentDetail)
def update_admission(
    admission_id: uuid.UUID,
    body: AdmissionUpdate,
    request: Request,
    principal: Principal = Depends(require(Permission.STUDENTS_WRITE)),
    db: Session = Depends(get_db),
) -> StudentDetail:
    admission = db.get(Admission, admission_id)
    if admission is None:
        raise not_found("Admission")
    principal.ensure_institution(admission.institution_id, "Admission")
    provided = {
        k: v
        for k, v in body.model_dump(exclude_unset=True, exclude={"reason"}).items()
        if v is not None
    }
    clean, errors = validate_partial(provided, today=date.today())
    if errors:
        raise AppError(
            422, "validation_error", "Some fields are invalid", [e.as_dict() for e in errors]
        )
    changed = [k for k, v in clean.items() if getattr(admission, k) != v]
    for key in changed:
        setattr(admission, key, clean[key])
    if changed:
        db.flush()
        run_validation(db, [admission.institution_id])
    audit.record(
        db,
        action="admission.updated",
        principal=principal,
        request=request,
        target_type="admission",
        target_id=admission.id,
        details={"changed_fields": changed, "reason": body.reason},
    )
    db.commit()
    return _student_detail(db, admission.student)


@router.post("/students/{student_id}/consent", response_model=StudentDetail)
def record_consent(
    student_id: uuid.UUID,
    body: ConsentUpdate,
    request: Request,
    principal: Principal = Depends(require(Permission.CONSENT_MANAGE)),
    db: Session = Depends(get_db),
) -> StudentDetail:
    student = _get_student(db, principal, student_id)
    current = current_consent(db, student.id)
    if current is None or current.status != body.status:
        db.add(
            ConsentRecord(
                student_id=student.id,
                institution_id=student.institution_id,
                purpose=CONSENT_PURPOSE,
                status=body.status,
                method="recorded_by_institution",
                note=body.note,
                recorded_by_id=principal.user_id,
            )
        )
        audit.record(
            db,
            action=f"consent.{body.status}",
            principal=principal,
            request=request,
            target_type="student",
            target_id=student.id,
            details={"purpose": CONSENT_PURPOSE},
        )
        db.commit()
    return _student_detail(db, student)


@router.post("/students/{student_id}/identity-check", response_model=VerificationOut)
def identity_check(
    student_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require(Permission.IDENTITY_CHECK)),
    db: Session = Depends(get_db),
) -> VerificationOut:
    student = _get_student(db, principal, student_id)
    identifier = decrypt_identifier(student.apaar_ciphertext)
    provider = get_provider()
    if identifier is None:
        outcome, message, simulated = "error", "Stored identifier could not be read.", True
    else:
        result = provider.verify(identifier)
        outcome, message, simulated = result.outcome, result.message, result.simulated
    attempt = VerificationAttempt(
        requested_by_id=principal.user_id,
        requester_role=principal.role,
        kind="identity_check",
        purpose="Institution record check",
        student_id=student.id,
        institution_id=student.institution_id,
        provider=provider.name,
        simulated=simulated,
        outcome=outcome,
        details={"message": message},
    )
    db.add(attempt)
    audit.record(
        db,
        action="verification.identity_check",
        principal=principal,
        request=request,
        target_type="student",
        target_id=student.id,
        institution_id=student.institution_id,
        details={"provider": provider.name, "simulated": simulated, "outcome": outcome},
    )
    db.commit()
    return _verification_out(attempt)


@router.post("/admissions/{admission_id}/certificate")
def generate_certificate(
    admission_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require(Permission.RECORDS_ISSUE)),
    db: Session = Depends(get_db),
) -> dict:
    admission = db.get(Admission, admission_id)
    if admission is None:
        raise not_found("Admission")
    principal.ensure_institution(admission.institution_id, "Admission")
    record, newly_issued = issue_record(db, admission, principal.user_id)
    student = admission.student
    programme: Programme = admission.programme
    institution = db.get(Institution, admission.institution_id)
    assert institution is not None
    audit.record(
        db,
        action="record.certificate_generated",
        principal=principal,
        request=request,
        target_type="admission",
        target_id=admission.id,
        details={"reference_code": record.reference_code, "newly_issued": newly_issued},
    )
    db.commit()
    return {
        "reference_code": record.reference_code,
        "issued_at": record.issued_at,
        "newly_issued": newly_issued,
        "digest_short": record.digest[:16].upper(),
        "institution": {
            "code": institution.code,
            "name": institution.name,
            "state": institution.state,
        },
        "student": {
            "full_name": student.full_name,
            "institution_student_id": student.institution_student_id,
            "date_of_birth": student.date_of_birth,
            "apaar_id": decrypt_identifier(student.apaar_ciphertext),
        },
        "programme": {"code": programme.code, "name": programme.name, "level": programme.level},
        "academic_year": admission.academic_year,
        "admission_date": admission.admission_date,
        "enrolment_status": admission.enrolment_status,
        "demo_notice": "DEMO DATA — NOT REAL STUDENT INFORMATION",
        "disclaimer": "Prototype record for demonstration using synthetic data. Not an official "
        "certificate or credential. The reference code confirms only that this record exists on "
        "this platform and is unchanged since issue.",
    }
