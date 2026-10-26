import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKey, utcnow
from app.models.student import Admission


class VerificationAttempt(UUIDPrimaryKey, Base):
    """Every verification request and its result, including the provider and whether the
    result was simulated. Raw identifiers are never stored here."""

    __tablename__ = "verification_attempts"

    requested_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    requester_role: Mapped[str] = mapped_column(String(32))
    kind: Mapped[str] = mapped_column(String(32))
    purpose: Mapped[str] = mapped_column(String(160))
    student_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("students.id"), index=True)
    institution_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("institutions.id"))
    provider: Mapped[str] = mapped_column(String(32))
    simulated: Mapped[bool]
    outcome: Mapped[str] = mapped_column(String(32))
    details: Mapped[dict[str, Any]] = mapped_column(default=dict)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)


class VerifiableRecord(UUIDPrimaryKey, Base):
    """A record reference issued for an admission (e.g. printed on a certificate).

    ``digest`` is a keyed HMAC over the record's key fields at issue time, so a verifier can
    tell whether the record has changed since issue. It is a prototype integrity check, not
    proof of identity and not an official credential.
    """

    __tablename__ = "verifiable_records"

    admission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("admissions.id"), index=True)
    institution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("institutions.id"))
    reference_code: Mapped[str] = mapped_column(String(24), unique=True)
    digest: Mapped[str] = mapped_column(String(64))
    issued_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    issued_at: Mapped[datetime] = mapped_column(default=utcnow)
    revoked_at: Mapped[datetime | None]

    admission: Mapped[Admission] = relationship()
