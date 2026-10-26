"""Human review of findings: permissions, lifecycle, history, audit, auto-resolution."""

import uuid

from sqlalchemy import select

from app.models import Admission, AuditEvent, Finding, Institution, ReviewAction
from tests.conftest import ARANYA_ADMIN, ARANYA_OPERATOR, CENTRAL


def run_demo_upload(as_user) -> None:
    c = as_user(ARANYA_OPERATOR)
    c.post(
        "/api/v1/uploads/students",
        files={"file": ("demo.csv", c.get("/api/v1/demo/sample-upload.csv").content, "text/csv")},
    )


def aranya_finding(db, rule_code: str) -> Finding:
    inst = db.scalar(select(Institution).where(Institution.code == "DEMO-INST-001"))
    return db.scalar(
        select(Finding).where(Finding.institution_id == inst.id, Finding.rule_code == rule_code)
    )


def act(c, finding_id: uuid.UUID, action: str, comment: str | None = "Checked the records"):
    return c.post(
        f"/api/v1/findings/{finding_id}/actions", json={"action": action, "comment": comment}
    )


def test_finding_detail_is_explainable(as_user, db):
    run_demo_upload(as_user)
    finding = aranya_finding(db, "INTAKE_EXCEEDED")
    detail = as_user(ARANYA_ADMIN).get(f"/api/v1/findings/{finding.id}").json()
    labels = {f["label"]: f["value"] for f in detail["evidence"]}
    assert labels["Regular-seat admissions counted"] == 65
    assert labels["Approved intake (configured)"] == 60
    assert detail["rule"]["assumption"]
    assert detail["recommended_action"]
    assert detail["history"][0]["action"] == "created"
    assert detail["history"][0]["actor_name"] == "System"


def test_operator_cannot_review(as_user, db):
    run_demo_upload(as_user)
    finding = aranya_finding(db, "CATEGORY_CONFLICT")
    operator = as_user(ARANYA_OPERATOR)
    assert operator.get(f"/api/v1/findings/{finding.id}").json()["allowed_actions"] == []
    assert act(operator, finding.id, "resolve").status_code == 403


def test_institution_admin_resolves_data_quality_finding(as_user, db):
    run_demo_upload(as_user)
    finding = aranya_finding(db, "CATEGORY_CONFLICT")
    admin = as_user(ARANYA_ADMIN)
    assert act(admin, finding.id, "resolve", None).status_code == 422
    assert act(admin, finding.id, "start_review", None).status_code == 200
    response = act(admin, finding.id, "resolve", "Category corrected in source records")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "resolved"
    assert [h["action"] for h in body["history"]] == ["created", "start_review", "resolve"]
    assert body["history"][-1]["actor_name"].startswith("Institution Admin")
    event = db.scalar(select(AuditEvent).where(AuditEvent.action == "finding.resolve"))
    assert event.details["to"] == "resolved"


def test_intake_findings_need_central_resolution(as_user, db):
    run_demo_upload(as_user)
    finding = aranya_finding(db, "INTAKE_EXCEEDED")
    admin = as_user(ARANYA_ADMIN)
    detail = admin.get(f"/api/v1/findings/{finding.id}").json()
    assert "resolve" not in detail["allowed_actions"]
    assert act(admin, finding.id, "resolve").status_code == 409
    assert (
        act(admin, finding.id, "escalate", "Need central confirmation").json()["status"]
        == "escalated"
    )

    central = as_user(CENTRAL)
    queue = central.get("/api/v1/findings", params={"status": "escalated"}).json()["items"]
    assert any(f["id"] == str(finding.id) for f in queue)
    resolved = act(central, finding.id, "resolve", "Approval for additional seats verified")
    assert resolved.json()["status"] == "resolved"
    assert act(admin, finding.id, "reopen", "Trying to reopen").status_code == 409


def test_fixing_the_data_auto_resolves_the_finding(as_user, db):
    run_demo_upload(as_user)
    finding = aranya_finding(db, "CATEGORY_CONFLICT")
    operator = as_user(ARANYA_OPERATOR)
    response = operator.patch(
        f"/api/v1/admissions/{finding.admission_id}",
        json={"foreign_national_status": False, "reason": "FN flag entered by mistake"},
    )
    assert response.status_code == 200
    db.expire_all()
    refreshed = db.get(Finding, finding.id)
    assert refreshed.status == "resolved"
    last = db.scalars(
        select(ReviewAction)
        .where(ReviewAction.finding_id == finding.id)
        .order_by(ReviewAction.created_at.desc())
    ).first()
    assert last.action == "auto_resolved" and last.actor_id is None


def test_dismissed_finding_is_not_raised_again_unless_evidence_changes(as_user, db):
    run_demo_upload(as_user)
    finding = aranya_finding(db, "MULTIPLE_ACTIVE_ADMISSIONS")
    admin = as_user(ARANYA_ADMIN)
    act(admin, finding.id, "dismiss", "Student is genuinely enrolled in both (synthetic)")
    run_demo_upload(as_user)  # re-validation runs again
    db.expire_all()
    active = db.scalars(
        select(Finding).where(
            Finding.dedupe_key == finding.dedupe_key,
            Finding.status.in_(("open", "in_review", "escalated")),
        )
    ).all()
    assert active == []


def test_raising_intake_resolves_the_overrun(as_user, db):
    run_demo_upload(as_user)
    finding = aranya_finding(db, "INTAKE_EXCEEDED")
    central = as_user(CENTRAL)
    response = central.put(
        f"/api/v1/programmes/{finding.programme_id}/intake/{finding.academic_year}",
        json={"approved_intake": 66, "supernumerary_seats": 3, "source": "synthetic-demo"},
    )
    assert response.status_code == 200
    db.expire_all()
    assert db.get(Finding, finding.id).status == "resolved"
    assert (
        as_user(ARANYA_ADMIN)
        .put(
            f"/api/v1/programmes/{finding.programme_id}/intake/{finding.academic_year}",
            json={"approved_intake": 100, "supernumerary_seats": 3},
        )
        .status_code
        == 403
    )


def test_queue_filters_and_summary(as_user, db):
    run_demo_upload(as_user)
    admin = as_user(ARANYA_ADMIN)
    high = admin.get("/api/v1/findings", params={"severity": "high"}).json()
    assert high["total"] >= 2 and all(f["severity"] == "high" for f in high["items"])
    summary = admin.get("/api/v1/findings/summary").json()
    assert summary["active_total"] == admin.get("/api/v1/findings").json()["total"]
    assert admin.get("/api/v1/findings", params={"status": "bogus"}).status_code == 422


def test_admission_count_matches_after_cancellation(as_user, db):
    run_demo_upload(as_user)
    finding = aranya_finding(db, "INTAKE_EXCEEDED")
    operator = as_user(ARANYA_OPERATOR)
    admissions = db.scalars(
        select(Admission).where(
            Admission.programme_id == finding.programme_id,
            Admission.academic_year == finding.academic_year,
            Admission.seat_type == "REGULAR",
        )
    ).all()[:5]
    for admission in admissions:
        assert (
            operator.patch(
                f"/api/v1/admissions/{admission.id}",
                json={"enrolment_status": "CANCELLED", "reason": "Seat surrendered"},
            ).status_code
            == 200
        )
    db.expire_all()
    assert db.get(Finding, finding.id).status == "resolved"
