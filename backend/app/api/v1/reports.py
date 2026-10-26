import uuid
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import Principal, require, scoped_institution_id
from app.api.v1.dashboard import resolve_year
from app.core.permissions import Permission
from app.db.base import utcnow
from app.db.session import get_db
from app.models import Finding, Institution, UploadBatch
from app.models.finding import FINDING_STATUSES
from app.services import audit
from app.services.dashboard import DEFINITIONS, programme_stats
from app.services.reporting import csv_response
from app.services.settings import load_policy
from app.services.validation.rules import RULES_BY_CODE

router = APIRouter(prefix="/reports", tags=["reports"])


def _scope_label(db: Session, institution_id: uuid.UUID | None) -> str:
    if institution_id is None:
        return "All institutions"
    inst = db.get(Institution, institution_id)
    return f"{inst.code} — {inst.name}" if inst else "Unknown institution"


def enrolment_report(
    db: Session, academic_year: str, institution_id: uuid.UUID | None
) -> dict[str, Any]:
    policy = load_policy(db)
    institutions = {i.id: i for i in db.scalars(select(Institution))}
    rows = []
    for stat in programme_stats(db, policy, academic_year, institution_id):
        inst = institutions[stat.institution_id]
        rows.append(
            {
                "institution_code": inst.code,
                "institution_name": inst.name,
                "state": inst.state,
                **stat.as_dict(),
            }
        )
    rows.sort(key=lambda r: (r["institution_code"], r["code"]))
    return {
        "report": "Enrolment versus approved intake",
        "academic_year": academic_year,
        "scope": _scope_label(db, institution_id),
        "generated_at": utcnow().isoformat(),
        "counted_statuses": policy.intake_policy.count_statuses,
        "rows": rows,
        "totals": {
            "approved_intake": sum(r["approved_intake"] or 0 for r in rows),
            "regular_enrolled": sum(r["regular_enrolled"] for r in rows),
            "supernumerary_enrolled": sum(r["supernumerary_enrolled"] for r in rows),
            "total_enrolled": sum(r["total_enrolled"] for r in rows),
            "programmes_over_intake": sum(1 for r in rows if r["status"] == "exceeded"),
        },
        "definitions": DEFINITIONS,
    }


def data_quality_report(db: Session, institution_id: uuid.UUID | None) -> dict[str, Any]:
    institutions = {i.id: i for i in db.scalars(select(Institution).order_by(Institution.code))}
    stmt = select(Finding.institution_id, Finding.rule_code, Finding.status, func.count()).group_by(
        Finding.institution_id, Finding.rule_code, Finding.status
    )
    upload_stmt = select(
        UploadBatch.institution_id,
        func.count(),
        func.sum(UploadBatch.total_rows),
        func.sum(UploadBatch.rejected_rows),
    ).group_by(UploadBatch.institution_id)
    if institution_id:
        stmt = stmt.where(Finding.institution_id == institution_id)
        upload_stmt = upload_stmt.where(UploadBatch.institution_id == institution_id)

    counts: dict[tuple[uuid.UUID, str], dict[str, int]] = defaultdict(
        lambda: dict.fromkeys(FINDING_STATUSES, 0)
    )
    for inst_id, rule, status, n in db.execute(stmt):
        counts[(inst_id, rule)][status] = n
    rows = []
    for (inst_id, rule), by_status in sorted(
        counts.items(), key=lambda kv: (institutions[kv[0][0]].code, kv[0][1])
    ):
        spec = RULES_BY_CODE.get(rule)
        rows.append(
            {
                "institution_code": institutions[inst_id].code,
                "institution_name": institutions[inst_id].name,
                "rule_code": rule,
                "rule_title": spec.title if spec else rule,
                "severity": spec.severity if spec else "",
                **by_status,
                "total": sum(by_status.values()),
            }
        )
    uploads = []
    for inst_id, batches, total_rows, rejected in db.execute(upload_stmt):
        total_rows, rejected = int(total_rows or 0), int(rejected or 0)
        uploads.append(
            {
                "institution_code": institutions[inst_id].code,
                "institution_name": institutions[inst_id].name,
                "uploads": batches,
                "rows_processed": total_rows,
                "rows_rejected": rejected,
                "acceptance_rate_pct": round(100 * (total_rows - rejected) / total_rows, 1)
                if total_rows
                else None,
            }
        )
    uploads.sort(key=lambda r: r["institution_code"])
    return {
        "report": "Data quality and findings",
        "scope": _scope_label(db, institution_id),
        "generated_at": utcnow().isoformat(),
        "findings": rows,
        "uploads": uploads,
        "note": "Findings are review signals produced by documented rules, not determinations "
        "of misconduct.",
    }


@router.get("/enrolment")
def get_enrolment_report(
    academic_year: str | None = Query(None, max_length=7),
    institution_id: uuid.UUID | None = None,
    principal: Principal = Depends(require(Permission.REPORTS_EXPORT)),
    db: Session = Depends(get_db),
) -> dict:
    return enrolment_report(
        db, resolve_year(db, academic_year), scoped_institution_id(principal, institution_id)
    )


@router.get("/enrolment.csv")
def export_enrolment_report(
    request: Request,
    academic_year: str | None = Query(None, max_length=7),
    institution_id: uuid.UUID | None = None,
    principal: Principal = Depends(require(Permission.REPORTS_EXPORT)),
    db: Session = Depends(get_db),
) -> Response:
    scoped = scoped_institution_id(principal, institution_id)
    report = enrolment_report(db, resolve_year(db, academic_year), scoped)
    audit.record(
        db,
        action="report.exported",
        principal=principal,
        request=request,
        details={
            "report": "enrolment",
            "academic_year": report["academic_year"],
            "scope": report["scope"],
            "rows": len(report["rows"]),
        },
    )
    db.commit()
    columns = [
        "institution_code",
        "institution_name",
        "state",
        "code",
        "name",
        "level",
        "approved_intake",
        "regular_enrolled",
        "supernumerary_seats",
        "supernumerary_enrolled",
        "total_enrolled",
        "utilisation_pct",
        "nri",
        "oci",
        "foreign_national",
        "status",
    ]
    return csv_response(
        columns,
        [[r[c] for c in columns] for r in report["rows"]],
        filename=f"enrolment-report-{report['academic_year']}.csv",
        preamble=[
            ["Report", report["report"]],
            ["Academic year", report["academic_year"]],
            ["Scope", report["scope"]],
            ["Generated at (UTC)", report["generated_at"]],
            ["Counted statuses", ", ".join(report["counted_statuses"])],
            ["Definition: utilisation_pct", DEFINITIONS["utilisation"]],
            ["Notice", "DEMO DATA — synthetic records only"],
        ],
    )


@router.get("/data-quality")
def get_data_quality_report(
    institution_id: uuid.UUID | None = None,
    principal: Principal = Depends(require(Permission.REPORTS_EXPORT)),
    db: Session = Depends(get_db),
) -> dict:
    return data_quality_report(db, scoped_institution_id(principal, institution_id))


@router.get("/data-quality.csv")
def export_data_quality_report(
    request: Request,
    institution_id: uuid.UUID | None = None,
    principal: Principal = Depends(require(Permission.REPORTS_EXPORT)),
    db: Session = Depends(get_db),
) -> Response:
    scoped = scoped_institution_id(principal, institution_id)
    report = data_quality_report(db, scoped)
    audit.record(
        db,
        action="report.exported",
        principal=principal,
        request=request,
        details={"report": "data-quality", "scope": report["scope"]},
    )
    db.commit()
    columns = [
        "institution_code",
        "institution_name",
        "rule_code",
        "rule_title",
        "severity",
        *FINDING_STATUSES,
        "total",
    ]
    return csv_response(
        columns,
        [[r[c] for c in columns] for r in report["findings"]],
        filename="data-quality-report.csv",
        preamble=[
            ["Report", report["report"]],
            ["Scope", report["scope"]],
            ["Generated at (UTC)", report["generated_at"]],
            ["Note", report["note"]],
            ["Notice", "DEMO DATA — synthetic records only"],
        ],
    )
