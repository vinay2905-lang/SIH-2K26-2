import pytest

from app.core import identifiers
from app.core.config import get_settings
from app.core.permissions import ROLE_PERMISSIONS, Permission, Role, has_permission
from app.core.security import hash_password, verify_password
from app.services.reporting import build_csv, safe_cell


def test_identifier_normalisation_and_masking():
    assert identifiers.normalize_identifier(" demo-apaar- 000123\n") == "DEMO-APAAR-000123"
    assert identifiers.mask("0123") == "••••••••0123"
    assert identifiers.mask(None) == ""


def test_fingerprint_is_keyed(monkeypatch: pytest.MonkeyPatch):
    value = "DEMO-APAAR-000123"
    first = identifiers.fingerprint(value)
    assert first == identifiers.fingerprint(value)
    assert value not in first
    monkeypatch.setattr(get_settings(), "identifier_hmac_key", "another-key")
    assert identifiers.fingerprint(value) != first


def test_encryption_round_trip_and_tamper_detection():
    token = identifiers.encrypt_identifier("DEMO-APAAR-000123")
    assert "DEMO-APAAR" not in token
    assert identifiers.decrypt_identifier(token) == "DEMO-APAAR-000123"
    assert identifiers.decrypt_identifier(token[:-4] + "AAAA") is None


def test_invalid_pattern_never_matches():
    assert identifiers.matches_format("x", "(") is False


def test_password_hashing():
    hashed = hash_password("correct horse")
    assert hashed != "correct horse"
    assert verify_password(hashed, "correct horse")
    assert not verify_password(hashed, "wrong")
    assert not verify_password(None, "anything")


@pytest.mark.parametrize("value", ["=1+1", "+cmd", "-2+3", "@SUM(A1)", "\tx", "\rx"])
def test_csv_formula_injection_is_neutralised(value: str):
    assert safe_cell(value) == "'" + value


def test_csv_keeps_numbers_and_booleans():
    assert safe_cell(-5) == -5
    assert safe_cell(True) == "Y"
    assert build_csv(["a"], [["=HYPERLINK()"]]).splitlines()[1] == "'=HYPERLINK()"


def test_permission_matrix_is_least_privilege():
    assert ROLE_PERMISSIONS[Role.AUTHORIZED_VERIFIER] == {Permission.VERIFY_LOOKUP}
    assert not has_permission("system_admin", Permission.STUDENTS_READ)
    assert not has_permission("institution_operator", Permission.FINDINGS_REVIEW)
    assert not has_permission("institution_admin", Permission.DASHBOARD_CENTRAL)
    assert not has_permission("unknown_role", Permission.STUDENTS_READ)
