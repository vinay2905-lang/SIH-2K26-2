"""Manual record entry and edits, reports, settings, and migration fidelity."""

import csv
import io
from datetime import date
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import select

from alembic import command
from app.models import Finding, Institution, Student
from app.seed import demo_years
from tests.conftest import ARANYA_ADMIN, ARANYA_OPERATOR, CENTRAL, SYSADMIN

CURRENT = demo_years(date.today())[1]


def new_record(**overrides) -> dict:
    body = {
        "programme_code": "BTECH-ME",
        "academic_year": CURRENT,
        "institution_student_id": "AITMANUAL01",
        "apaar_id": "DEMO-APAAR-555001",
        "full_name": "Sara D'Souza",
        "date_of_birth": "2008-05-20",
        "gender": "F",
        "admission_date": f"{CURRENT[:4]}-08-05",
        "seat_type": "REGULAR",
        "nri_category": False,
        "oci_status": False,
        "foreign_national_status": False,
        "nationality": "IN",
        "enrolment_status": "ENROLLED",
    }
    body.update(overrides)
    return body


def test_manual_record_entry(as_user, db):
    c = as_user(ARANYA_OPERATOR)
    created = c.post("/api/v1/students", json=new_record())
    assert created.status_code == 201
    assert created.json()["status"] == "created"
    same = c.post("/api/v1/students", json=new_record())
    assert same.json()["status"] == "unchanged"

    rejected = c.post(
        "/api/v1/students",
        json=new_record(
            apaar_id="DEMO-APAAR-55", date_of_birth="20/05/2008", institution_student_id="NEW02"
        ),
    )
    assert rejected.status_code == 422
    fields = {d["field"] for d in rejected.json()["error"]["details"]}
    assert fields == {"apaar_id", "date_of_birth"}


def test_identity_edit_is_audited_and_unique(as_user, db):
    c = as_user(ARANYA_OPERATOR)
    student_id = c.post("/api/v1/students", json=new_record()).json()["student_id"]
    response = c.patch(
        f"/api/v1/students/{student_id}",
        json={"full_name": "Sara Dsouza", "reason": "Name corrected per ID card"},
    )
    assert response.status_code == 200 and response.json()["full_name"] == "Sara Dsouza"
    clash = c.patch(
        f"/api/v1/students/{student_id}",
        json={"institution_student_id": "AIT25CSE001", "reason": "test clash"},
    )
    assert clash.status_code == 409
    assert c.patch(f"/api/v1/students/{student_id}", json={"full_name": "X"}).status_code == 422
    events = c.get("/api/v1/students/" + student_id).json()
    assert events["full_name"] == "Sara Dsouza"


def test_student_search_and_filters(as_user):
    c = as_user(ARANYA_OPERATOR)
    page = c.get("/api/v1/students", params={"q": "AIT", "page_size": 5}).json()
    assert page["total"] > 5 and len(page["items"]) == 5
    assert c.get("/api/v1/students", params={"q": "%_%"}).json()["total"] == 0
    filtered = c.get("/api/v1/students", params={"enrolment_status": "WITHDRAWN"}).json()
    assert filtered["total"] == 0


def test_enrolment_report_csv_matches_json_and_is_audited(as_user):
    c = as_user(CENTRAL)
    report = c.get("/api/v1/reports/enrolment").json()
    export = c.get("/api/v1/reports/enrolment.csv")
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("text/csv")
    lines = export.text.lstrip("\N{ZERO WIDTH NO-BREAK SPACE}").splitlines()
    header_index = next(i for i, line in enumerate(lines) if line.startswith("institution_code"))
    rows = list(csv.DictReader(io.StringIO("\n".join(lines[header_index:]))))
    assert len(rows) == len(report["rows"])
    assert sum(int(r["total_enrolled"]) for r in rows) == report["totals"]["total_enrolled"]
    assert any("DEMO DATA" in line for line in lines[:header_index])
    audit = c.get("/api/v1/audit-events", params={"action": "report."}).json()
    assert audit["items"][0]["action"] == "report.exported"


def test_central_dashboard_reconciles_with_reports(as_user):
    c = as_user(CENTRAL)
    dashboard = c.get("/api/v1/dashboard/central").json()
    report = c.get("/api/v1/reports/enrolment").json()
    assert dashboard["kpis"]["active_enrolments"] == report["totals"]["total_enrolled"]
    assert dashboard["kpis"]["institutions_total"] == 4
    assert dashboard["kpis"]["institutions_reporting"] == 2  # Aranya submits during the demo
    assert (
        sum(i["active_enrolments"] for i in dashboard["institutions"])
        == dashboard["kpis"]["active_enrolments"]
    )


def test_data_quality_report_scoped_for_institution(as_user):
    c = as_user(ARANYA_ADMIN)
    report = c.get("/api/v1/reports/data-quality").json()
    assert {r["institution_code"] for r in report["uploads"]} == {"DEMO-INST-001"}


def test_settings_change_revalidates(as_user, db):
    admin = as_user(SYSADMIN)
    settings = admin.get("/api/v1/settings").json()
    policy = settings["policy"]
    assert policy["identifier_format"]["pattern"] == r"DEMO-APAAR-\d{6}"

    bad = dict(policy, identifier_format={**policy["identifier_format"], "pattern": "("})
    assert admin.put("/api/v1/settings", json=bad).status_code == 422

    inst = db.scalar(select(Institution).where(Institution.code == "DEMO-INST-002"))
    before = db.scalar(
        select(Finding).where(
            Finding.institution_id == inst.id, Finding.rule_code == "CATEGORY_CONFLICT"
        )
    )
    assert before.status == "in_review"
    disabled = dict(policy, rules_enabled={"CATEGORY_CONFLICT": False})
    assert admin.put("/api/v1/settings", json=disabled).status_code == 200
    db.expire_all()
    assert db.get(Finding, before.id).status == "in_review"  # disabled rules leave findings

    stricter = dict(policy, consistency={**policy["consistency"], "min_age_at_admission": 30})
    response = admin.put("/api/v1/settings", json=stricter)
    assert response.status_code == 200
    assert db.scalar(select(Finding).where(Finding.rule_code == "AGE_AT_ADMISSION")) is not None


def test_identifier_format_setting_applies_to_uploads(as_user, db):
    admin = as_user(SYSADMIN)
    policy = admin.get("/api/v1/settings").json()["policy"]
    numeric = dict(
        policy, identifier_format={"pattern": r"\d{12}", "label": "12-digit numeric", "example": ""}
    )
    assert admin.put("/api/v1/settings", json=numeric).status_code == 200
    c = as_user(ARANYA_OPERATOR)
    rejected = c.post("/api/v1/students", json=new_record())
    assert rejected.status_code == 422
    assert rejected.json()["error"]["details"][0]["code"] == "IDENTIFIER_FORMAT_INVALID"


def test_migration_matches_models(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from app.core.config import get_settings

    backend = Path(__file__).resolve().parents[2]
    monkeypatch.setattr(get_settings(), "database_url", f"sqlite:///{tmp_path / 'm.db'}")
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    command.upgrade(config, "head")
    command.check(config)  # raises if models and migrations have drifted
    command.downgrade(config, "base")


def test_seeded_students_never_store_plain_identifiers(db):
    for student in db.scalars(select(Student).limit(50)):
        assert "DEMO-APAAR" not in student.apaar_ciphertext
        assert len(student.apaar_fingerprint) == 64
