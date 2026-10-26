import uuid

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPrimaryKey


class Institution(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "institutions"

    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    state: Mapped[str] = mapped_column(String(64))
    institution_type: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="active")

    programmes: Mapped[list["Programme"]] = relationship(
        back_populates="institution", order_by="Programme.code"
    )


class Programme(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "programmes"
    __table_args__ = (UniqueConstraint("institution_id", "code"),)

    institution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("institutions.id"), index=True)
    code: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(200))
    level: Mapped[str] = mapped_column(String(32))
    duration_years: Mapped[int] = mapped_column(default=4)
    status: Mapped[str] = mapped_column(String(16), default="active")

    institution: Mapped[Institution] = relationship(back_populates="programmes")
    intake_configurations: Mapped[list["IntakeConfiguration"]] = relationship(
        back_populates="programme", order_by="IntakeConfiguration.academic_year"
    )


class IntakeConfiguration(UUIDPrimaryKey, Timestamps, Base):
    """Approved intake for a programme in an academic year.

    Figures in the prototype are synthetic. ``source`` records where a figure came from so a
    real deployment can distinguish authoritative approvals from assumptions.
    """

    __tablename__ = "intake_configurations"
    __table_args__ = (
        UniqueConstraint("programme_id", "academic_year"),
        CheckConstraint("approved_intake >= 0", name="approved_intake_non_negative"),
        CheckConstraint("supernumerary_seats >= 0", name="supernumerary_non_negative"),
    )

    programme_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("programmes.id"), index=True)
    academic_year: Mapped[str] = mapped_column(String(7))
    approved_intake: Mapped[int]
    supernumerary_seats: Mapped[int] = mapped_column(default=0)
    source: Mapped[str] = mapped_column(String(64), default="synthetic-demo")
    notes: Mapped[str | None] = mapped_column(Text)
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))

    programme: Mapped[Programme] = relationship(back_populates="intake_configurations")
