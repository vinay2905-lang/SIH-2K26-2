import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPrimaryKey, utcnow
from app.models.institution import Institution, Programme
from app.models.student import Student
from app.models.user import User

ACTIVE_STATUSES = ("open", "in_review", "escalated")
CLOSED_STATUSES = ("resolved", "dismissed")
FINDING_STATUSES = ACTIVE_STATUSES + CLOSED_STATUSES


class Finding(UUIDPrimaryKey, Timestamps, Base):
    """An explainable validation flag that needs human review. Never a verdict of fraud."""

    __tablename__ = "findings"
    __table_args__ = (
        Index("ix_findings_queue", "institution_id", "status", "severity"),
        Index("ix_findings_dedupe", "dedupe_key", "status"),
    )

    institution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("institutions.id"))
    rule_code: Mapped[str] = mapped_column(String(64), index=True)
    category: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(16), default="open")
    title: Mapped[str] = mapped_column(String(200))
    reason: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict[str, Any]] = mapped_column(default=dict)
    # Details only central roles may see (e.g. which other institution holds a matching record).
    restricted_evidence: Mapped[dict[str, Any]] = mapped_column(default=dict)
    recommended_action: Mapped[str] = mapped_column(Text)
    dedupe_key: Mapped[str] = mapped_column(String(200))
    evidence_signature: Mapped[str] = mapped_column(String(64))
    target_type: Mapped[str] = mapped_column(String(32))
    student_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("students.id"), index=True)
    admission_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("admissions.id"))
    programme_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("programmes.id"))
    academic_year: Mapped[str | None] = mapped_column(String(7))
    source_batch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("upload_batches.id"))
    resolved_at: Mapped[datetime | None]
    resolved_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))

    institution: Mapped[Institution] = relationship()
    student: Mapped[Student | None] = relationship()
    programme: Mapped[Programme | None] = relationship()
    actions: Mapped[list["ReviewAction"]] = relationship(
        back_populates="finding", order_by="ReviewAction.created_at"
    )


class ReviewAction(UUIDPrimaryKey, Base):
    """Append-only history of what happened to a finding and who did it."""

    __tablename__ = "review_actions"

    finding_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("findings.id"), index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(32))
    from_status: Mapped[str | None] = mapped_column(String(16))
    to_status: Mapped[str | None] = mapped_column(String(16))
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    finding: Mapped[Finding] = relationship(back_populates="actions")
    actor: Mapped[User | None] = relationship()
