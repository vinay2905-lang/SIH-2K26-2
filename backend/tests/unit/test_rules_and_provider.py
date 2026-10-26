import uuid
from datetime import date

import pytest

from app.services.validation.rules import (
    RULES,
    AdmissionView,
    _age_on,
    _category_conflicts,
    academic_year_window,
)
from app.services.verification.adapter import SIMULATED_LABEL, MockApaarProvider


def view(**overrides) -> AdmissionView:
    base = dict(
        admission_id=uuid.uuid4(),
        student_id=uuid.uuid4(),
        institution_id=uuid.uuid4(),
        programme_id=uuid.uuid4(),
        programme_code="BTECH-CSE",
        programme_name="B.Tech CSE",
        academic_year="2026-27",
        admission_date=date(2026, 8, 1),
        seat_type="REGULAR",
        nri=False,
        oci=False,
        fn=False,
        enrolment_status="ENROLLED",
        institution_student_id="AIT001",
        apaar_last4="0123",
        date_of_birth=date(2008, 1, 1),
        nationality="IN",
    )
    base.update(overrides)
    return AdmissionView(**base)


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({}, []),
        (
            {"nri": True, "fn": True},
            [
                "Marked as both NRI and Foreign National",
                "Foreign National status with Indian nationality (IN)",
            ],
        ),
        (
            {"nri": True, "oci": True, "nationality": "US"},
            ["Marked as both NRI and OCI", "NRI category with non-Indian nationality (US)"],
        ),
        ({"oci": True}, ["OCI status with Indian nationality (IN)"]),
        ({"oci": True, "nationality": "US"}, []),
        ({"fn": True, "nationality": "NG"}, []),
    ],
)
def test_category_conflicts(overrides: dict, expected: list[str]):
    assert _category_conflicts(view(**overrides)) == expected


def test_age_on_date_handles_birthdays():
    assert _age_on(date(2008, 8, 2), date(2026, 8, 1)) == 17
    assert _age_on(date(2008, 8, 1), date(2026, 8, 1)) == 18


@pytest.mark.parametrize(
    ("year", "month", "start", "end"),
    [
        ("2026-27", 4, date(2026, 4, 1), date(2027, 3, 31)),
        ("2026-27", 1, date(2026, 1, 1), date(2026, 12, 31)),
        ("2026-27", 7, date(2026, 7, 1), date(2027, 6, 30)),
        ("2026-27", 12, date(2026, 12, 1), date(2027, 11, 30)),
    ],
)
def test_academic_year_window(year: str, month: int, start: date, end: date):
    assert academic_year_window(year, month) == (start, end)


def test_every_rule_is_explainable():
    for rule in RULES:
        assert rule.title and rule.checks and rule.rationale and rule.recommended_action
        assert rule.severity in {"high", "medium", "low"}
        assert rule.scope in {"institution", "global"}
        assert (rule.evaluate is None) == (rule.scope == "global")


@pytest.mark.parametrize(
    ("identifier", "outcome"),
    [
        ("DEMO-APAAR-000120", "match"),
        ("DEMO-APAAR-000127", "no_match"),
        ("DEMO-APAAR-000128", "unavailable"),
        ("DEMO-APAAR-000129", "pending"),
        ("DEMO-APAAR-00012X", "no_match"),
    ],
)
def test_mock_provider_is_deterministic_and_always_simulated(identifier: str, outcome: str):
    result = MockApaarProvider().verify(identifier)
    assert result.outcome == outcome
    assert result.simulated is True
    assert result.message.startswith(SIMULATED_LABEL)
