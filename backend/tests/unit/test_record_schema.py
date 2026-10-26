from datetime import date

import pytest

from app.services.ingestion.schema import academic_year_is_valid, validate_partial, validate_record
from app.services.settings import DEMO_IDENTIFIER_PATTERN

TODAY = date(2026, 10, 26)


def record(**overrides: str) -> dict[str, str]:
    base = {
        "institution_code": "DEMO-INST-001",
        "programme_code": "BTECH-CSE",
        "academic_year": "2026-27",
        "institution_student_id": "AIT26CSE001",
        "apaar_id": "DEMO-APAAR-000123",
        "full_name": "Aarav Sharma",
        "date_of_birth": "2008-03-14",
        "gender": "M",
        "admission_date": "2026-08-01",
        "seat_type": "REGULAR",
        "nri_category": "N",
        "oci_status": "N",
        "foreign_national_status": "N",
        "nationality": "IN",
        "enrolment_status": "ENROLLED",
    }
    base.update(overrides)
    return base


def check(raw: dict[str, str]):
    return validate_record(
        raw, identifier_pattern=DEMO_IDENTIFIER_PATTERN, identifier_label="demo", today=TODAY
    )


def codes(raw: dict[str, str]) -> set[tuple[str | None, str]]:
    _, errors = check(raw)
    return {(e.field, e.code) for e in errors}


def test_valid_record_is_normalised():
    parsed, errors = check(
        record(
            apaar_id=" demo-apaar-000123 ",
            full_name="  Aarav   Sharma ",
            seat_type="regular",
            nri_category="yes",
        )
    )
    assert errors == []
    assert parsed is not None
    assert parsed.apaar_id == "DEMO-APAAR-000123"
    assert parsed.full_name == "Aarav Sharma"
    assert parsed.seat_type == "REGULAR"
    assert parsed.nri_category is True


def test_missing_apaar_id_has_its_own_code():
    assert ("apaar_id", "IDENTIFIER_MISSING") in codes(record(apaar_id=""))


@pytest.mark.parametrize("value", ["DEMO-APAAR-12AB", "123456789012", "DEMO-APAAR-0001234"])
def test_malformed_apaar_id_is_rejected(value: str):
    assert ("apaar_id", "IDENTIFIER_FORMAT_INVALID") in codes(record(apaar_id=value))


def test_error_message_never_echoes_identifier():
    _, errors = check(record(apaar_id="DEMO-APAAR-12AB"))
    assert all("12AB" not in e.message for e in errors)


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("date_of_birth", "14/03/2008", "INVALID_DATE"),
        ("date_of_birth", "2008-02-30", "INVALID_DATE"),
        ("date_of_birth", "2027-01-01", "INVALID_DATE"),
        ("admission_date", "2026-12-01", "INVALID_DATE"),
        ("academic_year", "2026-28", "INVALID_ACADEMIC_YEAR"),
        ("seat_type", "MANAGEMENT", "INVALID_VALUE"),
        ("nri_category", "maybe", "INVALID_VALUE"),
        ("nationality", "IND", "INVALID_VALUE"),
        ("gender", "X", "INVALID_VALUE"),
        ("enrolment_status", "ACTIVE", "INVALID_VALUE"),
        ("full_name", "R2D2", "INVALID_VALUE"),
        ("institution_student_id", "AIT 001", "INVALID_VALUE"),
        ("programme_code", "", "REQUIRED_FIELD_MISSING"),
    ],
)
def test_field_rules(field: str, value: str, code: str):
    assert (field, code) in codes(record(**{field: value}))


def test_gender_is_optional():
    parsed, errors = check(record(gender=""))
    assert errors == [] and parsed is not None and parsed.gender is None


def test_overlong_value_is_rejected():
    assert ("full_name", "VALUE_TOO_LONG") in codes(record(full_name="A" * 600))


@pytest.mark.parametrize(
    ("value", "valid"),
    [
        ("2025-26", True),
        ("2099-00", True),
        ("2025-27", False),
        ("25-26", False),
        ("1999-00", False),
    ],
)
def test_academic_year_format(value: str, valid: bool):
    assert academic_year_is_valid(value) is valid


def test_partial_validation_for_edits():
    clean, errors = validate_partial(
        {
            "full_name": " Meera  Joshi ",
            "date_of_birth": "2008-01-01",
            "seat_type": "regular",
            "nri_category": True,
        },
        today=TODAY,
    )
    assert errors == []
    assert clean == {
        "full_name": "Meera Joshi",
        "date_of_birth": date(2008, 1, 1),
        "seat_type": "REGULAR",
        "nri_category": True,
    }
    _, errors = validate_partial({"apaar_id": "x"}, today=TODAY)
    assert errors[0].code == "INVALID_VALUE"
