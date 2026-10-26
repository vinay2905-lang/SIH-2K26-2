"""The canonical student-admission record contract, shared by CSV upload and the entry form.

Every rejection carries a stable code, the field and a human-readable reason. Messages never
echo the submitted identifier value.
"""

import re
from dataclasses import dataclass
from datetime import date

from app.core.identifiers import matches_format, normalize_identifier

SEAT_TYPES = ("REGULAR", "SUPERNUMERARY")
ENROLMENT_STATUSES = ("ENROLLED", "CANCELLED", "WITHDRAWN")
GENDERS = ("F", "M", "O")
YES_NO = {"Y": True, "YES": True, "N": False, "NO": False}
MAX_CELL_LENGTH = 500


@dataclass(frozen=True)
class Column:
    name: str
    required: bool
    description: str
    example: str


COLUMNS: tuple[Column, ...] = (
    Column("institution_code", True, "Your institution's code on this platform", "DEMO-INST-001"),
    Column("programme_code", True, "Programme code configured for your institution", "BTECH-CSE"),
    Column("academic_year", True, "Academic year of admission, YYYY-YY", "2025-26"),
    Column(
        "institution_student_id",
        True,
        "Student ID assigned by your institution (letters, digits, / _ -)",
        "AIT25CSE001",
    ),
    Column("apaar_id", True, "APAAR identifier in the configured format", "DEMO-APAAR-000123"),
    Column("full_name", True, "Student's full name", "Aarav Sharma"),
    Column("date_of_birth", True, "Date of birth, YYYY-MM-DD", "2007-03-14"),
    Column("gender", False, "F, M or O (optional)", "M"),
    Column("admission_date", True, "Date of admission, YYYY-MM-DD", "2025-08-01"),
    Column("seat_type", True, "REGULAR or SUPERNUMERARY (as sanctioned)", "REGULAR"),
    Column("nri_category", True, "Admitted under NRI category: Y or N", "N"),
    Column("oci_status", True, "Overseas Citizen of India: Y or N", "N"),
    Column("foreign_national_status", True, "Foreign National (FN): Y or N", "N"),
    Column("nationality", True, "ISO 3166-1 alpha-2 country code", "IN"),
    Column("enrolment_status", True, "ENROLLED, CANCELLED or WITHDRAWN", "ENROLLED"),
)
COLUMN_NAMES = tuple(c.name for c in COLUMNS)
REQUIRED_COLUMNS = tuple(c.name for c in COLUMNS if c.required)
IDENTITY_FIELDS = ("institution_student_id", "full_name", "date_of_birth", "gender", "nationality")

_ACADEMIC_YEAR = re.compile(r"(\d{4})-(\d{2})")
_STUDENT_ID = re.compile(r"[A-Za-z0-9/_-]{1,64}")
_COUNTRY = re.compile(r"[A-Z]{2}")
_CODE = re.compile(r"[A-Za-z0-9_-]{1,32}")
_NAME_PUNCTUATION = set(" .'-")


@dataclass(frozen=True)
class RowError:
    code: str
    message: str
    field: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {"field": self.field, "code": self.code, "message": self.message}


@dataclass(frozen=True)
class StudentRecordInput:
    institution_code: str
    programme_code: str
    academic_year: str
    institution_student_id: str
    apaar_id: str  # normalised; never log or echo
    full_name: str
    date_of_birth: date
    gender: str | None
    admission_date: date
    seat_type: str
    nri_category: bool
    oci_status: bool
    foreign_national_status: bool
    nationality: str
    enrolment_status: str


def academic_year_is_valid(value: str) -> bool:
    match = _ACADEMIC_YEAR.fullmatch(value)
    if not match:
        return False
    start, end = int(match.group(1)), int(match.group(2))
    return 2000 <= start <= 2100 and end == (start + 1) % 100


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) else None
    except ValueError:
        return None


def _valid_name(value: str) -> bool:
    if not 2 <= len(value) <= 160 or not any(ch.isalpha() for ch in value):
        return False
    return all(ch.isalpha() or ch in _NAME_PUNCTUATION for ch in value)


def validate_partial(
    values: dict[str, object], *, today: date
) -> tuple[dict[str, object], list[RowError]]:
    """Validate a subset of identity/admission fields for an edit. Booleans pass through."""
    clean: dict[str, object] = {}
    errors: list[RowError] = []
    for name, raw in values.items():
        if isinstance(raw, bool):
            clean[name] = raw
            continue
        value = (str(raw) if raw is not None else "").strip()
        if name == "gender":
            gender = value.upper() or None
            if gender and gender not in GENDERS:
                errors.append(RowError("INVALID_VALUE", "Gender must be F, M or O", name))
            clean[name] = gender
            continue
        if not value:
            errors.append(RowError("REQUIRED_FIELD_MISSING", f"{name} is required", name))
            continue
        if name == "institution_student_id":
            if not _STUDENT_ID.fullmatch(value):
                errors.append(
                    RowError(
                        "INVALID_VALUE", "Student ID may contain only letters, digits, / _ -", name
                    )
                )
            clean[name] = value
        elif name == "full_name":
            value = " ".join(value.split())
            if not _valid_name(value):
                errors.append(
                    RowError(
                        "INVALID_VALUE", "Name may contain only letters, spaces and . ' -", name
                    )
                )
            clean[name] = value
        elif name in ("date_of_birth", "admission_date"):
            parsed = _parse_date(value)
            if parsed is None:
                errors.append(RowError("INVALID_DATE", "Use the date format YYYY-MM-DD", name))
            elif (name == "date_of_birth" and parsed >= today) or parsed > today:
                errors.append(RowError("INVALID_DATE", "Date cannot be in the future", name))
            clean[name] = parsed
        elif name == "nationality":
            if not _COUNTRY.fullmatch(value.upper()):
                errors.append(
                    RowError("INVALID_VALUE", "Nationality must be a two-letter country code", name)
                )
            clean[name] = value.upper()
        elif name == "seat_type":
            if value.upper() not in SEAT_TYPES:
                errors.append(
                    RowError("INVALID_VALUE", "Seat type must be REGULAR or SUPERNUMERARY", name)
                )
            clean[name] = value.upper()
        elif name == "enrolment_status":
            if value.upper() not in ENROLMENT_STATUSES:
                errors.append(
                    RowError(
                        "INVALID_VALUE", "Status must be ENROLLED, CANCELLED or WITHDRAWN", name
                    )
                )
            clean[name] = value.upper()
        else:
            errors.append(RowError("INVALID_VALUE", "Field cannot be edited here", name))
    return clean, errors


def validate_record(
    raw: dict[str, str | None],
    *,
    identifier_pattern: str,
    identifier_label: str,
    today: date,
) -> tuple[StudentRecordInput | None, list[RowError]]:
    """Validate one record's fields in isolation (no database lookups)."""
    errors: list[RowError] = []
    values: dict[str, str] = {}
    for column in COLUMNS:
        value = (raw.get(column.name) or "").strip()
        if len(value) > MAX_CELL_LENGTH:
            errors.append(RowError("VALUE_TOO_LONG", "Value is too long", column.name))
            value = ""
        values[column.name] = value

    for name in REQUIRED_COLUMNS:
        if not values[name] and not any(e.field == name for e in errors):
            if name == "apaar_id":
                errors.append(RowError("IDENTIFIER_MISSING", "APAAR ID is missing", name))
            else:
                errors.append(RowError("REQUIRED_FIELD_MISSING", f"{name} is required", name))

    def invalid(field: str, message: str, code: str = "INVALID_VALUE") -> None:
        errors.append(RowError(code, message, field))

    institution_code = values["institution_code"].upper()
    if institution_code and not _CODE.fullmatch(institution_code):
        invalid("institution_code", "Institution code contains unsupported characters")
    programme_code = values["programme_code"].upper()
    if programme_code and not _CODE.fullmatch(programme_code):
        invalid("programme_code", "Programme code contains unsupported characters")

    academic_year = values["academic_year"]
    if academic_year and not academic_year_is_valid(academic_year):
        invalid("academic_year", "Academic year must look like 2025-26", "INVALID_ACADEMIC_YEAR")

    student_id = values["institution_student_id"]
    if student_id and not _STUDENT_ID.fullmatch(student_id):
        invalid("institution_student_id", "Student ID may contain only letters, digits, / _ -")

    apaar = normalize_identifier(values["apaar_id"])
    if values["apaar_id"] and not matches_format(apaar, identifier_pattern):
        invalid(
            "apaar_id",
            f"APAAR ID does not match the configured format ({identifier_label})",
            "IDENTIFIER_FORMAT_INVALID",
        )

    full_name = " ".join(values["full_name"].split())
    if full_name and not _valid_name(full_name):
        invalid("full_name", "Name may contain only letters, spaces and . ' -")

    dob = _parse_date(values["date_of_birth"]) if values["date_of_birth"] else None
    if values["date_of_birth"] and dob is None:
        invalid("date_of_birth", "Use the date format YYYY-MM-DD", "INVALID_DATE")
    elif dob and dob >= today:
        invalid("date_of_birth", "Date of birth must be in the past", "INVALID_DATE")

    admission_date = _parse_date(values["admission_date"]) if values["admission_date"] else None
    if values["admission_date"] and admission_date is None:
        invalid("admission_date", "Use the date format YYYY-MM-DD", "INVALID_DATE")
    elif admission_date and admission_date > today:
        invalid("admission_date", "Admission date cannot be in the future", "INVALID_DATE")

    gender = values["gender"].upper() or None
    if gender and gender not in GENDERS:
        invalid("gender", "Gender must be F, M or O (or left blank)")

    seat_type = values["seat_type"].upper()
    if seat_type and seat_type not in SEAT_TYPES:
        invalid("seat_type", "Seat type must be REGULAR or SUPERNUMERARY")

    flags: dict[str, bool] = {}
    for name in ("nri_category", "oci_status", "foreign_national_status"):
        raw_flag = values[name].upper()
        if raw_flag and raw_flag not in YES_NO:
            invalid(name, f"{name} must be Y or N")
        flags[name] = YES_NO.get(raw_flag, False)

    nationality = values["nationality"].upper()
    if nationality and not _COUNTRY.fullmatch(nationality):
        invalid("nationality", "Nationality must be a two-letter country code such as IN")

    status = values["enrolment_status"].upper()
    if status and status not in ENROLMENT_STATUSES:
        invalid("enrolment_status", "Status must be ENROLLED, CANCELLED or WITHDRAWN")

    if errors:
        return None, errors

    assert dob is not None and admission_date is not None
    return (
        StudentRecordInput(
            institution_code=institution_code,
            programme_code=programme_code,
            academic_year=academic_year,
            institution_student_id=student_id,
            apaar_id=apaar,
            full_name=full_name,
            date_of_birth=dob,
            gender=gender,
            admission_date=admission_date,
            seat_type=seat_type,
            nri_category=flags["nri_category"],
            oci_status=flags["oci_status"],
            foreign_national_status=flags["foreign_national_status"],
            nationality=nationality,
            enrolment_status=status,
        ),
        [],
    )
