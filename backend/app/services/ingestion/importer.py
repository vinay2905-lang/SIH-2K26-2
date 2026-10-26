"""Applies validated records to the database.

Matching policy (documented in docs/csv-import.md):

* A student is identified within an institution by APAAR ID (keyed fingerprint).
* An admission is identified by (student, programme, academic year). Re-submitting the same
  admission updates it if admission fields changed, and is a no-op otherwise, so repeat
  uploads are idempotent.
* Identity details (student ID, name, date of birth, gender, nationality) are never silently
  overwritten by an upload. A row whose identity differs from the stored record is rejected so
  the change can be made deliberately on the student page, where it is audited.
"""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.identifiers import encrypt_identifier, fingerprint, last4, normalize_identifier
from app.models import Admission, Institution, Programme, Student
from app.services.ingestion.schema import RowError, StudentRecordInput, validate_record

_CHUNK = 500

ADMISSION_FIELDS = (
    "admission_date",
    "seat_type",
    "nri_category",
    "oci_status",
    "foreign_national_status",
    "enrolment_status",
)


@dataclass
class ApplyResult:
    status: str  # created | updated | unchanged | rejected
    errors: list[RowError] = field(default_factory=list)
    student: Student | None = None
    admission: Admission | None = None
    changed_fields: list[str] = field(default_factory=list)


def _identity_differences(student: Student, record: StudentRecordInput) -> list[str]:
    differences = []
    if student.institution_student_id != record.institution_student_id:
        differences.append("institution_student_id")
    if student.full_name.casefold() != record.full_name.casefold():
        differences.append("full_name")
    if student.date_of_birth != record.date_of_birth:
        differences.append("date_of_birth")
    if (student.gender or None) != record.gender:
        differences.append("gender")
    if student.nationality != record.nationality:
        differences.append("nationality")
    return differences


class RecordImporter:
    """Stateful over one batch so rows can reference students created earlier in the batch."""

    def __init__(
        self,
        db: Session,
        institution: Institution,
        *,
        actor_id: uuid.UUID | None,
        batch_id: uuid.UUID | None,
        identifier_pattern: str,
        identifier_label: str,
        today: date,
    ) -> None:
        self.db = db
        self.institution = institution
        self.actor_id = actor_id
        self.batch_id = batch_id
        self.identifier_pattern = identifier_pattern
        self.identifier_label = identifier_label
        self.today = today
        self.programmes = {
            p.code: p
            for p in db.scalars(select(Programme).where(Programme.institution_id == institution.id))
        }
        self._students_by_fp: dict[str, Student | None] = {}
        self._students_by_sid: dict[str, Student | None] = {}
        self._admissions: dict[tuple[uuid.UUID, uuid.UUID, str], Admission | None] = {}
        self._admissions_loaded: set[uuid.UUID] = set()
        # Within-file tracking: admission key -> first line, fingerprint -> first record.
        self._seen_admissions: dict[tuple[str, str, str], int] = {}
        self._seen_identity: dict[str, tuple[int, StudentRecordInput]] = {}
        self._seen_student_ids: dict[str, tuple[int, str]] = {}

    def prefetch(self, rows: Iterable[dict[str, str]]) -> None:
        """Load every existing student and admission the batch can touch in a few queries,
        instead of several queries per row."""
        fingerprints, student_ids = set(), set()
        for raw in rows:
            identifier = normalize_identifier(raw.get("apaar_id"))
            if identifier:
                fingerprints.add(fingerprint(identifier))
            sid = (raw.get("institution_student_id") or "").strip()
            if sid:
                student_ids.add(sid)
        found: dict[uuid.UUID, Student] = {}
        for column, values in (
            (Student.apaar_fingerprint, sorted(fingerprints)),
            (Student.institution_student_id, sorted(student_ids)),
        ):
            for start in range(0, len(values), _CHUNK):
                for student in self.db.scalars(
                    select(Student).where(
                        Student.institution_id == self.institution.id,
                        column.in_(values[start : start + _CHUNK]),
                    )
                ):
                    found[student.id] = student
        for fp in fingerprints:
            self._students_by_fp.setdefault(fp, None)
        for sid in student_ids:
            self._students_by_sid.setdefault(sid, None)
        for student in found.values():
            self._students_by_fp[student.apaar_fingerprint] = student
            self._students_by_sid[student.institution_student_id] = student

        ids = sorted(found, key=str)
        for start in range(0, len(ids), _CHUNK):
            chunk = ids[start : start + _CHUNK]
            for admission in self.db.scalars(
                select(Admission).where(Admission.student_id.in_(chunk))
            ):
                key = (admission.student_id, admission.programme_id, admission.academic_year)
                self._admissions[key] = admission
            self._admissions_loaded.update(chunk)

    def _admission(
        self, student_id: uuid.UUID, programme_id: uuid.UUID, academic_year: str
    ) -> Admission | None:
        key = (student_id, programme_id, academic_year)
        if key not in self._admissions and student_id not in self._admissions_loaded:
            self._admissions[key] = self.db.scalar(
                select(Admission).where(
                    Admission.student_id == student_id,
                    Admission.programme_id == programme_id,
                    Admission.academic_year == academic_year,
                )
            )
        return self._admissions.get(key)

    def _student_by_fp(self, fp: str) -> Student | None:
        if fp not in self._students_by_fp:
            self._students_by_fp[fp] = self.db.scalar(
                select(Student).where(
                    Student.institution_id == self.institution.id, Student.apaar_fingerprint == fp
                )
            )
        return self._students_by_fp[fp]

    def _student_by_sid(self, sid: str) -> Student | None:
        if sid not in self._students_by_sid:
            self._students_by_sid[sid] = self.db.scalar(
                select(Student).where(
                    Student.institution_id == self.institution.id,
                    Student.institution_student_id == sid,
                )
            )
        return self._students_by_sid[sid]

    def apply(self, raw: dict[str, str | None], line_number: int | None = None) -> ApplyResult:
        record, errors = validate_record(
            raw,
            identifier_pattern=self.identifier_pattern,
            identifier_label=self.identifier_label,
            today=self.today,
        )
        if record is None:
            return ApplyResult("rejected", errors)
        context_errors = self._context_errors(record, line_number)
        if context_errors:
            return ApplyResult("rejected", context_errors)
        return self._upsert(record)

    def _context_errors(
        self, record: StudentRecordInput, line_number: int | None
    ) -> list[RowError]:
        errors: list[RowError] = []
        if record.institution_code != self.institution.code:
            errors.append(
                RowError(
                    "INSTITUTION_MISMATCH",
                    "institution_code does not match your institution. You can submit records only "
                    "for your own institution",
                    "institution_code",
                )
            )
        programme = self.programmes.get(record.programme_code)
        if programme is None:
            errors.append(
                RowError(
                    "UNKNOWN_PROGRAMME",
                    f"Programme {record.programme_code} is not configured for your institution",
                    "programme_code",
                )
            )
        if errors:
            return errors

        fp = fingerprint(record.apaar_id)
        admission_key = (fp, record.programme_code, record.academic_year)
        if admission_key in self._seen_admissions:
            return [
                RowError(
                    "DUPLICATE_IN_FILE",
                    f"Same APAAR ID, programme and academic year as line "
                    f"{self._seen_admissions[admission_key]}; only the first occurrence is used",
                    "apaar_id",
                )
            ]
        seen = self._seen_identity.get(fp)
        if seen is not None:
            differing = [
                f
                for f in (
                    "institution_student_id",
                    "full_name",
                    "date_of_birth",
                    "gender",
                    "nationality",
                )
                if getattr(seen[1], f) != getattr(record, f)
            ]
            if differing:
                return [
                    RowError(
                        "IDENTITY_MISMATCH",
                        f"Same APAAR ID as line {seen[0]} but different {', '.join(differing)}",
                        "apaar_id",
                    )
                ]
        seen_sid = self._seen_student_ids.get(record.institution_student_id)
        if seen_sid is not None and seen_sid[1] != fp:
            return [
                RowError(
                    "STUDENT_ID_CONFLICT",
                    f"Student ID is used on line {seen_sid[0]} with a different APAAR ID",
                    "institution_student_id",
                )
            ]

        existing = self._student_by_fp(fp)
        if existing is not None:
            differing = _identity_differences(existing, record)
            if differing:
                return [
                    RowError(
                        "IDENTITY_MISMATCH",
                        f"Differs from the existing record for this APAAR ID in: "
                        f"{', '.join(differing)}. Correct the file, or update the record on the "
                        f"student page",
                        differing[0],
                    )
                ]
        else:
            holder = self._student_by_sid(record.institution_student_id)
            if holder is not None:
                return [
                    RowError(
                        "STUDENT_ID_CONFLICT",
                        "This student ID is already assigned to a different APAAR ID "
                        "in your records",
                        "institution_student_id",
                    )
                ]

        if line_number is not None:
            self._seen_admissions[admission_key] = line_number
            self._seen_identity.setdefault(fp, (line_number, record))
            self._seen_student_ids.setdefault(record.institution_student_id, (line_number, fp))
        return []

    def _upsert(self, record: StudentRecordInput) -> ApplyResult:
        fp = fingerprint(record.apaar_id)
        programme = self.programmes[record.programme_code]
        student = self._student_by_fp(fp)
        if student is None:
            student = Student(
                id=uuid.uuid4(),
                institution_id=self.institution.id,
                institution_student_id=record.institution_student_id,
                apaar_fingerprint=fp,
                apaar_ciphertext=encrypt_identifier(record.apaar_id),
                apaar_last4=last4(record.apaar_id),
                full_name=record.full_name,
                date_of_birth=record.date_of_birth,
                gender=record.gender,
                nationality=record.nationality,
                created_by_id=self.actor_id,
                updated_by_id=self.actor_id,
            )
            self.db.add(student)
            self._students_by_fp[fp] = student
            self._students_by_sid[record.institution_student_id] = student
            self._admissions_loaded.add(student.id)  # a new student has no stored admissions
            admission = None
        else:
            admission = self._admission(student.id, programme.id, record.academic_year)

        values = {name: getattr(record, name) for name in ADMISSION_FIELDS}
        if admission is None:
            admission = Admission(
                id=uuid.uuid4(),
                student_id=student.id,
                institution_id=self.institution.id,
                programme_id=programme.id,
                academic_year=record.academic_year,
                source_batch_id=self.batch_id,
                **values,
            )
            self.db.add(admission)
            self._admissions[(student.id, programme.id, record.academic_year)] = admission
            return ApplyResult("created", student=student, admission=admission)

        changed = [name for name, value in values.items() if getattr(admission, name) != value]
        if not changed:
            return ApplyResult("unchanged", student=student, admission=admission)
        for name in changed:
            setattr(admission, name, values[name])
        admission.source_batch_id = self.batch_id or admission.source_batch_id
        student.updated_by_id = self.actor_id
        return ApplyResult("updated", student=student, admission=admission, changed_fields=changed)
