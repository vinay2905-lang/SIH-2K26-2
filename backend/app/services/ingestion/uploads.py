"""Upload orchestration: parse -> validate rows -> persist accepted rows -> run rules.

Batch semantics (docs/csv-import.md): valid rows are persisted and invalid rows are reported,
inside ONE transaction together with the batch summary and the rule results. If anything
unexpected fails, the transaction is rolled back and a FAILED batch is recorded on its own,
so an upload never leaves partially written, unreported state.
"""

import hashlib
import logging
import time
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.models import Institution, UploadBatch, UploadRowResult
from app.services.ingestion.csv_parser import parse_csv
from app.services.ingestion.importer import RecordImporter
from app.services.settings import load_policy
from app.services.validation.engine import run_validation

logger = logging.getLogger("app.uploads")


def _batch_status(accepted: int, rejected: int) -> str:
    if accepted and rejected:
        return "partial"
    if accepted:
        return "completed"
    return "rejected"


def process_upload(
    db: Session,
    *,
    institution: Institution,
    uploaded_by_id: uuid.UUID | None,
    filename: str,
    content: bytes,
    max_rows: int,
    today: date | None = None,
) -> UploadBatch:
    started = time.perf_counter()
    today = today or date.today()
    sha = hashlib.sha256(content).hexdigest()
    previous = db.scalar(
        select(UploadBatch)
        .where(UploadBatch.institution_id == institution.id)
        .where(UploadBatch.file_sha256 == sha)
        .where(UploadBatch.status.in_(("completed", "partial")))
        .order_by(UploadBatch.created_at.desc())
        .limit(1)
    )

    batch = UploadBatch(
        id=uuid.uuid4(),
        institution_id=institution.id,
        uploaded_by_id=uploaded_by_id,
        original_filename=filename,
        file_sha256=sha,
        status="processing",
        repeat_of_batch_id=previous.id if previous else None,
    )
    db.add(batch)

    parsed = parse_csv(content, max_rows=max_rows)
    warnings = list(parsed.warnings)
    if previous is not None:
        warnings.append(
            {
                "code": "REPEAT_UPLOAD",
                "message": "An identical file was uploaded before. Rows were re-checked; records "
                "that already match were left unchanged.",
            }
        )
    batch.warnings = warnings
    batch.skipped_blank_rows = parsed.blank_rows

    if not parsed.ok:
        batch.status = "rejected"
        batch.file_errors = parsed.file_errors
        batch.total_rows = len(parsed.rows)
        batch.completed_at = utcnow()
        batch.processing_ms = int((time.perf_counter() - started) * 1000)
        db.flush()
        return batch

    policy = load_policy(db)
    importer = RecordImporter(
        db,
        institution,
        actor_id=uploaded_by_id,
        batch_id=batch.id,
        identifier_pattern=policy.identifier_format.pattern,
        identifier_label=policy.identifier_format.label,
        today=today,
    )
    db.flush()

    counts = {"created": 0, "updated": 0, "unchanged": 0, "rejected": 0}
    for row in parsed.rows:
        if row.errors:
            result_status, errors, student, admission = "rejected", row.errors, None, None
        else:
            result = importer.apply(row.values, row.line_number)
            result_status, errors = result.status, result.errors
            student, admission = result.student, result.admission
        counts[result_status] += 1
        label = (row.values.get("institution_student_id") or "").strip()[:64] or None
        db.add(
            UploadRowResult(
                batch_id=batch.id,
                row_number=row.line_number,
                status=result_status,
                row_label=label,
                errors=[e.as_dict() for e in errors],
                student_id=student.id if student else None,
                admission_id=admission.id if admission else None,
            )
        )

    accepted = counts["created"] + counts["updated"] + counts["unchanged"]
    batch.total_rows = len(parsed.rows)
    batch.created_rows = counts["created"]
    batch.updated_rows = counts["updated"]
    batch.unchanged_rows = counts["unchanged"]
    batch.rejected_rows = counts["rejected"]
    batch.status = _batch_status(accepted, counts["rejected"])
    db.flush()

    if accepted:
        stats = run_validation(db, [institution.id], batch_id=batch.id, policy=policy)
        batch.findings_opened = stats.opened

    batch.completed_at = utcnow()
    batch.processing_ms = int((time.perf_counter() - started) * 1000)
    db.flush()
    return batch


def record_failed_upload(
    db: Session,
    *,
    institution_id: uuid.UUID,
    uploaded_by_id: uuid.UUID | None,
    filename: str,
    content: bytes,
) -> UploadBatch:
    batch = UploadBatch(
        institution_id=institution_id,
        uploaded_by_id=uploaded_by_id,
        original_filename=filename,
        file_sha256=hashlib.sha256(content).hexdigest(),
        status="failed",
        file_errors=[
            {
                "code": "PROCESSING_FAILED",
                "message": "The upload could not be processed. No records were saved. Try again or "
                "contact support with the request ID.",
            }
        ],
        completed_at=utcnow(),
    )
    db.add(batch)
    return batch
