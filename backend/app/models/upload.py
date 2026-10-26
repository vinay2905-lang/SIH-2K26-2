import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKey, utcnow
from app.models.user import User


class UploadBatch(UUIDPrimaryKey, Base):
    """One CSV submission. Raw file contents are not retained; only counts and row results."""

    __tablename__ = "upload_batches"

    institution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("institutions.id"), index=True)
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    original_filename: Mapped[str] = mapped_column(String(255))
    file_sha256: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(16))
    total_rows: Mapped[int] = mapped_column(default=0)
    created_rows: Mapped[int] = mapped_column(default=0)
    updated_rows: Mapped[int] = mapped_column(default=0)
    unchanged_rows: Mapped[int] = mapped_column(default=0)
    rejected_rows: Mapped[int] = mapped_column(default=0)
    skipped_blank_rows: Mapped[int] = mapped_column(default=0)
    findings_opened: Mapped[int] = mapped_column(default=0)
    file_errors: Mapped[list[Any]] = mapped_column(default=list)
    warnings: Mapped[list[Any]] = mapped_column(default=list)
    repeat_of_batch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("upload_batches.id"))
    processing_ms: Mapped[int | None]
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    completed_at: Mapped[datetime | None]

    uploaded_by: Mapped[User | None] = relationship()


class UploadRowResult(UUIDPrimaryKey, Base):
    """Outcome for one CSV row. Stores the institutional student ID as a label, never the
    APAAR identifier or the full row payload."""

    __tablename__ = "upload_row_results"
    __table_args__ = (UniqueConstraint("batch_id", "row_number"),)

    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("upload_batches.id"), index=True)
    row_number: Mapped[int]
    status: Mapped[str] = mapped_column(String(16))
    row_label: Mapped[str | None] = mapped_column(String(64))
    errors: Mapped[list[Any]] = mapped_column(default=list)
    student_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("students.id"))
    admission_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("admissions.id"))
