import uuid
from datetime import date, datetime

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPrimaryKey, utcnow
from app.models.institution import Institution, Programme


class Student(UUIDPrimaryKey, Timestamps, Base):
    """A person as recorded by one institution.

    Each institution owns its own student records (tenant isolation). The same person at two
    institutions shares an identifier fingerprint, which is how potential cross-institution
    duplicates are found without merging records across tenants.
    """

    __tablename__ = "students"
    __table_args__ = (
        UniqueConstraint("institution_id", "institution_student_id"),
        UniqueConstraint("institution_id", "apaar_fingerprint"),
    )

    institution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("institutions.id"), index=True)
    institution_student_id: Mapped[str] = mapped_column(String(64))
    apaar_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    apaar_ciphertext: Mapped[str] = mapped_column(Text)
    apaar_last4: Mapped[str] = mapped_column(String(4))
    full_name: Mapped[str] = mapped_column(String(160))
    date_of_birth: Mapped[date]
    gender: Mapped[str | None] = mapped_column(String(1))
    nationality: Mapped[str] = mapped_column(String(2))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))

    institution: Mapped[Institution] = relationship()
    admissions: Mapped[list["Admission"]] = relationship(
        back_populates="student", order_by="Admission.academic_year"
    )


class Admission(UUIDPrimaryKey, Timestamps, Base):
    """One admission/enrolment of a student in a programme for an academic year."""

    __tablename__ = "admissions"
    __table_args__ = (
        UniqueConstraint("student_id", "programme_id", "academic_year"),
        Index("ix_admissions_scope", "institution_id", "academic_year", "enrolment_status"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("students.id"), index=True)
    institution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("institutions.id"))
    programme_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("programmes.id"), index=True)
    academic_year: Mapped[str] = mapped_column(String(7))
    admission_date: Mapped[date]
    seat_type: Mapped[str] = mapped_column(String(16))
    nri_category: Mapped[bool] = mapped_column(default=False)
    oci_status: Mapped[bool] = mapped_column(default=False)
    foreign_national_status: Mapped[bool] = mapped_column(default=False)
    enrolment_status: Mapped[str] = mapped_column(String(16))
    source_batch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("upload_batches.id"))

    student: Mapped[Student] = relationship(back_populates="admissions")
    programme: Mapped[Programme] = relationship()


class ConsentRecord(UUIDPrimaryKey, Base):
    """Append-only consent history. The latest row per (student, purpose) is current.

    In the prototype the institution records consent on the student's behalf; a production
    system would capture it from the student directly. Recording a status does not by itself
    establish legal sufficiency.
    """

    __tablename__ = "consent_records"

    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("students.id"), index=True)
    institution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("institutions.id"))
    purpose: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    method: Mapped[str] = mapped_column(String(64))
    note: Mapped[str | None] = mapped_column(Text)
    recorded_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
