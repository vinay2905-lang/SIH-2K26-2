import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, UploadFile
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import Principal, get_principal, require, scoped_institution_id
from app.core.config import get_settings
from app.core.errors import AppError, not_found
from app.core.permissions import Permission
from app.db.session import get_db
from app.models import Institution, UploadBatch, UploadRowResult
from app.schemas.common import InstitutionRef, Page, PageParams
from app.services import audit
from app.services.ingestion.csv_parser import template_csv
from app.services.ingestion.uploads import process_upload, record_failed_upload
from app.services.reporting import csv_response

logger = logging.getLogger("app.uploads")
router = APIRouter(tags=["uploads"])


class UploaderOut(BaseModel):
    full_name: str
    email: str


class BatchOut(BaseModel):
    id: uuid.UUID
    institution: InstitutionRef
    original_filename: str
    status: str
    total_rows: int
    created_rows: int
    updated_rows: int
    unchanged_rows: int
    rejected_rows: int
    skipped_blank_rows: int
    findings_opened: int
    file_errors: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    repeat_of_batch_id: uuid.UUID | None
    processing_ms: int | None
    uploaded_by: UploaderOut | None
    created_at: datetime
    completed_at: datetime | None


class RowOut(BaseModel):
    row_number: int
    status: str
    row_label: str | None
    errors: list[dict[str, Any]]
    student_id: uuid.UUID | None


def _batch_out(batch: UploadBatch, institution: Institution) -> BatchOut:
    return BatchOut(
        id=batch.id,
        institution=InstitutionRef.model_validate(institution),
        original_filename=batch.original_filename,
        status=batch.status,
        total_rows=batch.total_rows,
        created_rows=batch.created_rows,
        updated_rows=batch.updated_rows,
        unchanged_rows=batch.unchanged_rows,
        rejected_rows=batch.rejected_rows,
        skipped_blank_rows=batch.skipped_blank_rows,
        findings_opened=batch.findings_opened,
        file_errors=batch.file_errors or [],
        warnings=batch.warnings or [],
        repeat_of_batch_id=batch.repeat_of_batch_id,
        processing_ms=batch.processing_ms,
        uploaded_by=UploaderOut(
            full_name=batch.uploaded_by.full_name, email=batch.uploaded_by.email
        )
        if batch.uploaded_by
        else None,
        created_at=batch.created_at,
        completed_at=batch.completed_at,
    )


def _get_batch(db: Session, principal: Principal, batch_id: uuid.UUID) -> UploadBatch:
    batch = db.get(UploadBatch, batch_id)
    if batch is None:
        raise not_found("Upload")
    principal.ensure_institution(batch.institution_id, "Upload")
    return batch


def _safe_filename(name: str | None) -> str:
    base = (name or "upload.csv").replace("\\", "/").rsplit("/", 1)[-1]
    cleaned = "".join(ch for ch in base if ch.isprintable())[:255]
    return cleaned or "upload.csv"


@router.get("/uploads/template.csv", response_class=PlainTextResponse)
def upload_template(principal: Principal = Depends(get_principal)) -> PlainTextResponse:
    return PlainTextResponse(
        template_csv(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="student-upload-template.csv"'},
    )


@router.post("/uploads/students", response_model=BatchOut, status_code=201)
def upload_students(
    file: UploadFile,
    request: Request,
    principal: Principal = Depends(require(Permission.UPLOADS_CREATE)),
    db: Session = Depends(get_db),
) -> BatchOut:
    settings = get_settings()
    if principal.institution_id is None:
        raise AppError(403, "forbidden", "Only institution users can upload student data")
    filename = _safe_filename(file.filename)
    if not filename.lower().endswith(".csv"):
        raise AppError(415, "unsupported_media_type", "Upload a .csv file")

    content = file.file.read(settings.upload_max_bytes + 1)
    if len(content) > settings.upload_max_bytes:
        raise AppError(
            413,
            "payload_too_large",
            f"File is larger than {settings.upload_max_bytes // (1024 * 1024)} MB",
        )

    institution = db.get(Institution, principal.institution_id)
    assert institution is not None
    try:
        batch = process_upload(
            db,
            institution=institution,
            uploaded_by_id=principal.user_id,
            filename=filename,
            content=content,
            max_rows=settings.upload_max_rows,
        )
        audit.record(
            db,
            action="upload.processed",
            principal=principal,
            request=request,
            target_type="upload_batch",
            target_id=batch.id,
            details={
                "status": batch.status,
                "total_rows": batch.total_rows,
                "rejected_rows": batch.rejected_rows,
                "findings_opened": batch.findings_opened,
            },
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception(
            "Upload processing failed (request_id=%s)", getattr(request.state, "request_id", None)
        )
        failed = record_failed_upload(
            db,
            institution_id=institution.id,
            uploaded_by_id=principal.user_id,
            filename=filename,
            content=content,
        )
        audit.record(
            db,
            action="upload.processed",
            principal=principal,
            request=request,
            target_type="upload_batch",
            target_id=failed.id,
            outcome="failure",
        )
        db.commit()
        raise AppError(
            500,
            "upload_failed",
            "The upload could not be processed. No records were saved",
            {"batch_id": str(failed.id)},
        ) from None
    db.refresh(batch)
    return _batch_out(batch, institution)


@router.get("/uploads", response_model=Page[BatchOut])
def list_uploads(
    institution_id: uuid.UUID | None = None,
    status: str | None = Query(None, max_length=16),
    paging: PageParams = Depends(),
    principal: Principal = Depends(require(Permission.UPLOADS_READ)),
    db: Session = Depends(get_db),
) -> Page[BatchOut]:
    stmt = select(UploadBatch, Institution).join(
        Institution, UploadBatch.institution_id == Institution.id
    )
    scoped = scoped_institution_id(principal, institution_id)
    if scoped is not None:
        stmt = stmt.where(UploadBatch.institution_id == scoped)
    if status:
        stmt = stmt.where(UploadBatch.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(
        stmt.options(selectinload(UploadBatch.uploaded_by))
        .order_by(UploadBatch.created_at.desc())
        .offset(paging.offset)
        .limit(paging.page_size)
    ).all()
    return Page(
        items=[_batch_out(b, i) for b, i in rows],
        total=total,
        page=paging.page,
        page_size=paging.page_size,
    )


@router.get("/uploads/{batch_id}", response_model=BatchOut)
def get_upload(
    batch_id: uuid.UUID,
    principal: Principal = Depends(require(Permission.UPLOADS_READ)),
    db: Session = Depends(get_db),
) -> BatchOut:
    batch = _get_batch(db, principal, batch_id)
    institution = db.get(Institution, batch.institution_id)
    assert institution is not None
    return _batch_out(batch, institution)


@router.get("/uploads/{batch_id}/rows", response_model=Page[RowOut])
def get_upload_rows(
    batch_id: uuid.UUID,
    status: str | None = Query(None, max_length=16),
    paging: PageParams = Depends(),
    principal: Principal = Depends(require(Permission.UPLOADS_READ)),
    db: Session = Depends(get_db),
) -> Page[RowOut]:
    _get_batch(db, principal, batch_id)
    stmt = select(UploadRowResult).where(UploadRowResult.batch_id == batch_id)
    if status:
        stmt = stmt.where(UploadRowResult.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(UploadRowResult.row_number).offset(paging.offset).limit(paging.page_size)
    ).all()
    return Page(
        items=[
            RowOut(
                row_number=r.row_number,
                status=r.status,
                row_label=r.row_label,
                errors=r.errors or [],
                student_id=r.student_id,
            )
            for r in rows
        ],
        total=total,
        page=paging.page,
        page_size=paging.page_size,
    )


@router.get("/uploads/{batch_id}/errors.csv")
def download_upload_errors(
    batch_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require(Permission.UPLOADS_READ)),
    db: Session = Depends(get_db),
) -> Response:
    batch = _get_batch(db, principal, batch_id)
    rows: list[list[Any]] = []
    for error in batch.file_errors or []:
        rows.append(["file", "", "", error.get("code"), error.get("message")])
    for result in db.scalars(
        select(UploadRowResult)
        .where(UploadRowResult.batch_id == batch_id, UploadRowResult.status == "rejected")
        .order_by(UploadRowResult.row_number)
    ):
        for error in result.errors or []:
            rows.append(
                [
                    result.row_number,
                    result.row_label or "",
                    error.get("field") or "",
                    error.get("code"),
                    error.get("message"),
                ]
            )
    audit.record(
        db,
        action="upload.errors_downloaded",
        principal=principal,
        request=request,
        target_type="upload_batch",
        target_id=batch.id,
        institution_id=batch.institution_id,
    )
    db.commit()
    return csv_response(
        ["line", "institution_student_id", "field", "code", "message"],
        rows,
        filename=f"upload-errors-{str(batch.id)[:8]}.csv",
    )
