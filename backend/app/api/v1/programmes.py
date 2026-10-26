import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import Principal, require, scoped_institution_id
from app.core.errors import AppError, not_found
from app.core.permissions import Permission
from app.db.session import get_db
from app.models import Admission, Institution, IntakeConfiguration, Programme, UploadBatch
from app.schemas.common import InstitutionRef, ORMModel
from app.services import audit
from app.services.ingestion.schema import academic_year_is_valid
from app.services.validation.engine import run_validation

router = APIRouter(tags=["institutions & programmes"])


class IntakeOut(ORMModel):
    id: uuid.UUID
    academic_year: str
    approved_intake: int
    supernumerary_seats: int
    source: str
    notes: str | None
    updated_at: datetime


class ProgrammeOut(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    level: str
    duration_years: int
    status: str
    institution: InstitutionRef
    intake_configurations: list[IntakeOut]


class IntakeUpsert(BaseModel):
    approved_intake: int = Field(ge=0, le=10_000)
    supernumerary_seats: int = Field(ge=0, le=1_000)
    source: str = Field(default="synthetic-demo", min_length=1, max_length=64)
    notes: str | None = Field(default=None, max_length=500)


class InstitutionOut(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    state: str
    institution_type: str
    status: str
    programme_count: int
    student_admissions: int
    last_upload_at: datetime | None


@router.get("/institutions", response_model=list[InstitutionOut])
def list_institutions(
    principal: Principal = Depends(require(Permission.INSTITUTIONS_READ)),
    db: Session = Depends(get_db),
) -> list[InstitutionOut]:
    programme_counts = dict(
        db.execute(
            select(Programme.institution_id, func.count()).group_by(Programme.institution_id)
        ).all()
    )
    admission_counts = dict(
        db.execute(
            select(Admission.institution_id, func.count()).group_by(Admission.institution_id)
        ).all()
    )
    last_uploads = dict(
        db.execute(
            select(UploadBatch.institution_id, func.max(UploadBatch.created_at)).group_by(
                UploadBatch.institution_id
            )
        ).all()
    )
    return [
        InstitutionOut(
            id=i.id,
            code=i.code,
            name=i.name,
            state=i.state,
            institution_type=i.institution_type,
            status=i.status,
            programme_count=programme_counts.get(i.id, 0),
            student_admissions=admission_counts.get(i.id, 0),
            last_upload_at=last_uploads.get(i.id),
        )
        for i in db.scalars(select(Institution).order_by(Institution.code))
    ]


@router.get("/programmes", response_model=list[ProgrammeOut])
def list_programmes(
    institution_id: uuid.UUID | None = None,
    principal: Principal = Depends(require(Permission.PROGRAMMES_READ)),
    db: Session = Depends(get_db),
) -> list[Programme]:
    scoped = scoped_institution_id(principal, institution_id)
    stmt = (
        select(Programme)
        .join(Institution)
        .options(selectinload(Programme.intake_configurations), selectinload(Programme.institution))
        .order_by(Institution.code, Programme.code)
    )
    if scoped is not None:
        stmt = stmt.where(Programme.institution_id == scoped)
    return list(db.scalars(stmt))


@router.put("/programmes/{programme_id}/intake/{academic_year}", response_model=ProgrammeOut)
def upsert_intake(
    programme_id: uuid.UUID,
    academic_year: str,
    body: IntakeUpsert,
    request: Request,
    principal: Principal = Depends(require(Permission.INTAKE_MANAGE)),
    db: Session = Depends(get_db),
) -> Programme:
    programme = db.get(Programme, programme_id)
    if programme is None:
        raise not_found("Programme")
    if not academic_year_is_valid(academic_year):
        raise AppError(422, "validation_error", "Academic year must look like 2025-26")

    config = db.scalar(
        select(IntakeConfiguration).where(
            IntakeConfiguration.programme_id == programme_id,
            IntakeConfiguration.academic_year == academic_year,
        )
    )
    previous = None
    if config is None:
        config = IntakeConfiguration(
            programme_id=programme_id, academic_year=academic_year, **body.model_dump()
        )
        db.add(config)
    else:
        previous = {
            "approved_intake": config.approved_intake,
            "supernumerary_seats": config.supernumerary_seats,
        }
        for key, value in body.model_dump().items():
            setattr(config, key, value)
    config.updated_by_id = principal.user_id
    db.flush()

    run_validation(db, [programme.institution_id])
    audit.record(
        db,
        action="intake.updated",
        principal=principal,
        request=request,
        target_type="programme",
        target_id=programme.id,
        institution_id=programme.institution_id,
        details={
            "academic_year": academic_year,
            "previous": previous,
            "approved_intake": body.approved_intake,
            "supernumerary_seats": body.supernumerary_seats,
        },
    )
    db.commit()
    db.refresh(programme)
    return programme
