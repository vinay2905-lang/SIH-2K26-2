"""Dashboard and report metrics, all computed from persisted records.

Metric definitions (also returned to the UI and documented in docs/api-contract.md):

* Active enrolments: admissions in the academic year whose status is a configured counted
  status (default ENROLLED). A student admitted to two programmes counts twice; distinct
  students are reported separately.
* Approved intake: sum of configured approved intake for programmes in that year.
* Utilisation: regular-seat active enrolments / approved intake.
* Open findings: findings with status open, in review or escalated (all years).
"""

import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.models import (
    Admission,
    ConsentRecord,
    Finding,
    Institution,
    IntakeConfiguration,
    Programme,
    UploadBatch,
)
from app.models.finding import ACTIVE_STATUSES
from app.services.records import CONSENT_PURPOSE
from app.services.settings import PolicySettings
from app.services.validation.rules import CATEGORY_LABELS

DEFINITIONS = {
    "active_enrolments": "Admissions in the academic year whose status is counted "
    "(configured; default ENROLLED). A student in two programmes counts twice.",
    "distinct_students": "Distinct students with at least one counted admission in the year.",
    "approved_intake": "Sum of configured approved intake for the year (synthetic demo figures).",
    "utilisation": "Regular-seat active enrolments divided by approved intake.",
    "open_findings": "Findings that are open, in review or escalated, across all years.",
    "acceptance_rate": "Accepted rows / processed rows across all uploads.",
}


def _pct(numerator: int, denominator: int) -> float | None:
    return round(100 * numerator / denominator, 1) if denominator else None


@dataclass
class ProgrammeStat:
    programme_id: uuid.UUID
    institution_id: uuid.UUID
    code: str
    name: str
    level: str
    approved_intake: int | None = None
    supernumerary_seats: int | None = None
    regular: int = 0
    supernumerary: int = 0
    nri: int = 0
    oci: int = 0
    fn: int = 0
    students: set[uuid.UUID] = field(default_factory=set)

    @property
    def status(self) -> str:
        if self.approved_intake is None:
            return "not_configured" if self.regular or self.supernumerary else "no_intake"
        over = self.regular > self.approved_intake or (
            self.supernumerary > (self.supernumerary_seats or 0)
        )
        return "exceeded" if over else "within"

    def as_dict(self) -> dict[str, Any]:
        return {
            "programme_id": str(self.programme_id),
            "code": self.code,
            "name": self.name,
            "level": self.level,
            "approved_intake": self.approved_intake,
            "supernumerary_seats": self.supernumerary_seats,
            "regular_enrolled": self.regular,
            "supernumerary_enrolled": self.supernumerary,
            "total_enrolled": self.regular + self.supernumerary,
            "utilisation_pct": _pct(self.regular, self.approved_intake or 0),
            "nri": self.nri,
            "oci": self.oci,
            "foreign_national": self.fn,
            "status": self.status,
        }


def programme_stats(
    db: Session,
    policy: PolicySettings,
    academic_year: str,
    institution_id: uuid.UUID | None = None,
) -> list[ProgrammeStat]:
    programmes = select(Programme)
    if institution_id:
        programmes = programmes.where(Programme.institution_id == institution_id)
    stats = {
        p.id: ProgrammeStat(p.id, p.institution_id, p.code, p.name, p.level)
        for p in db.scalars(programmes.order_by(Programme.code))
    }
    if not stats:
        return []
    for config in db.scalars(
        select(IntakeConfiguration).where(
            IntakeConfiguration.academic_year == academic_year,
            IntakeConfiguration.programme_id.in_(stats.keys()),
        )
    ):
        stats[config.programme_id].approved_intake = config.approved_intake
        stats[config.programme_id].supernumerary_seats = config.supernumerary_seats

    admissions = select(
        Admission.programme_id,
        Admission.student_id,
        Admission.seat_type,
        Admission.nri_category,
        Admission.oci_status,
        Admission.foreign_national_status,
    ).where(
        Admission.academic_year == academic_year,
        Admission.enrolment_status.in_(policy.intake_policy.count_statuses),
    )
    if institution_id:
        admissions = admissions.where(Admission.institution_id == institution_id)
    for programme_id, student_id, seat_type, nri, oci, fn in db.execute(admissions):
        stat = stats.get(programme_id)
        if stat is None:
            continue
        if seat_type == "SUPERNUMERARY":
            stat.supernumerary += 1
        else:
            stat.regular += 1
        stat.nri += int(nri)
        stat.oci += int(oci)
        stat.fn += int(fn)
        stat.students.add(student_id)
    return list(stats.values())


def _finding_counts(db: Session, institution_id: uuid.UUID | None = None) -> dict[str, Any]:
    stmt = select(Finding.institution_id, Finding.category, Finding.severity, Finding.status).where(
        Finding.status.in_(ACTIVE_STATUSES)
    )
    if institution_id:
        stmt = stmt.where(Finding.institution_id == institution_id)
    by_institution: Counter[uuid.UUID] = Counter()
    high_by_institution: Counter[uuid.UUID] = Counter()
    by_category: Counter[str] = Counter()
    by_severity: Counter[str] = Counter()
    escalated = 0
    cross = 0
    for inst, category, severity, status in db.execute(stmt):
        by_institution[inst] += 1
        by_category[category] += 1
        by_severity[severity] += 1
        if severity == "high":
            high_by_institution[inst] += 1
        if status == "escalated":
            escalated += 1
        if category == "CROSS_INSTITUTION":
            cross += 1
    return {
        "by_institution": by_institution,
        "high_by_institution": high_by_institution,
        "by_category": [
            {"category": c, "label": label, "count": by_category.get(c, 0)}
            for c, label in CATEGORY_LABELS.items()
        ],
        "by_severity": {s: by_severity.get(s, 0) for s in ("high", "medium", "low")},
        "total": sum(by_institution.values()),
        "escalated": escalated,
        "cross_institution": cross,
    }


def _upload_rows(db: Session, institution_id: uuid.UUID | None = None) -> dict[uuid.UUID, Any]:
    stmt = select(
        UploadBatch.institution_id,
        func.sum(UploadBatch.created_rows + UploadBatch.updated_rows + UploadBatch.unchanged_rows),
        func.sum(UploadBatch.rejected_rows),
        func.max(UploadBatch.created_at),
        func.count(),
    ).group_by(UploadBatch.institution_id)
    if institution_id:
        stmt = stmt.where(UploadBatch.institution_id == institution_id)
    return {row[0]: row[1:] for row in db.execute(stmt)}


def _summarise(stats: list[ProgrammeStat]) -> dict[str, Any]:
    regular = sum(s.regular for s in stats)
    supernumerary = sum(s.supernumerary for s in stats)
    intake = sum(s.approved_intake or 0 for s in stats)
    students: set[uuid.UUID] = set()
    for s in stats:
        students |= s.students
    return {
        "active_enrolments": regular + supernumerary,
        "distinct_students": len(students),
        "regular_enrolled": regular,
        "supernumerary_enrolled": supernumerary,
        "approved_intake": intake,
        "supernumerary_seats": sum(s.supernumerary_seats or 0 for s in stats),
        "utilisation_pct": _pct(regular, intake),
        "programmes_over_intake": sum(1 for s in stats if s.status == "exceeded"),
        "programmes_not_configured": sum(1 for s in stats if s.status == "not_configured"),
        "nri": sum(s.nri for s in stats),
        "oci": sum(s.oci for s in stats),
        "foreign_national": sum(s.fn for s in stats),
    }


def institution_dashboard(
    db: Session, policy: PolicySettings, institution: Institution, academic_year: str
) -> dict[str, Any]:
    stats = programme_stats(db, policy, academic_year, institution.id)
    summary = _summarise(stats)
    findings = _finding_counts(db, institution.id)
    uploads = _upload_rows(db, institution.id).get(institution.id)
    accepted, rejected = (int(uploads[0] or 0), int(uploads[1] or 0)) if uploads else (0, 0)

    students_in_year: set[uuid.UUID] = set()
    for s in stats:
        students_in_year |= s.students
    consent_granted = 0
    if students_in_year:
        latest: dict[uuid.UUID, str] = {}
        for record in db.scalars(
            select(ConsentRecord)
            .where(
                ConsentRecord.institution_id == institution.id,
                ConsentRecord.purpose == CONSENT_PURPOSE,
            )
            .order_by(ConsentRecord.created_at)
        ):
            latest[record.student_id] = record.status
        consent_granted = sum(1 for sid in students_in_year if latest.get(sid) == "granted")

    recent = db.scalars(
        select(UploadBatch)
        .where(UploadBatch.institution_id == institution.id)
        .order_by(UploadBatch.created_at.desc())
        .limit(5)
    ).all()
    return {
        "academic_year": academic_year,
        "institution": {
            "id": str(institution.id),
            "code": institution.code,
            "name": institution.name,
        },
        "kpis": {
            **summary,
            "open_findings": findings["total"],
            "high_severity_open": findings["by_severity"]["high"],
            "escalated": findings["escalated"],
            "rows_accepted": accepted,
            "rows_rejected": rejected,
            "acceptance_rate_pct": _pct(accepted, accepted + rejected),
            "consent_granted": consent_granted,
            "consent_coverage_pct": _pct(consent_granted, len(students_in_year)),
        },
        "programmes": [s.as_dict() for s in stats],
        "findings_by_category": findings["by_category"],
        "findings_by_severity": findings["by_severity"],
        "recent_uploads": [
            {
                "id": str(b.id),
                "filename": b.original_filename,
                "status": b.status,
                "total_rows": b.total_rows,
                "rejected_rows": b.rejected_rows,
                "findings_opened": b.findings_opened,
                "created_at": b.created_at.isoformat(),
            }
            for b in recent
        ],
        "counted_statuses": policy.intake_policy.count_statuses,
        "definitions": DEFINITIONS,
        "generated_at": utcnow().isoformat(),
    }


def central_dashboard(db: Session, policy: PolicySettings, academic_year: str) -> dict[str, Any]:
    stats = programme_stats(db, policy, academic_year)
    by_institution: dict[uuid.UUID, list[ProgrammeStat]] = defaultdict(list)
    for s in stats:
        by_institution[s.institution_id].append(s)
    findings = _finding_counts(db)
    uploads = _upload_rows(db)

    institutions = []
    for inst in db.scalars(select(Institution).order_by(Institution.code)):
        summary = _summarise(by_institution.get(inst.id, []))
        upload = uploads.get(inst.id)
        accepted, rejected = (int(upload[0] or 0), int(upload[1] or 0)) if upload else (0, 0)
        institutions.append(
            {
                "id": str(inst.id),
                "code": inst.code,
                "name": inst.name,
                "state": inst.state,
                "institution_type": inst.institution_type,
                "active_enrolments": summary["active_enrolments"],
                "approved_intake": summary["approved_intake"],
                "regular_enrolled": summary["regular_enrolled"],
                "utilisation_pct": summary["utilisation_pct"],
                "programmes_over_intake": summary["programmes_over_intake"],
                "open_findings": findings["by_institution"].get(inst.id, 0),
                "high_severity_open": findings["high_by_institution"].get(inst.id, 0),
                "acceptance_rate_pct": _pct(accepted, accepted + rejected),
                "last_upload_at": upload[2].isoformat() if upload and upload[2] else None,
                "uploads": int(upload[3]) if upload else 0,
                "reporting": summary["active_enrolments"] > 0,
            }
        )

    totals = _summarise(stats)
    since = utcnow() - timedelta(days=30)
    daily: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for created_at, accepted, rejected in db.execute(
        select(
            UploadBatch.created_at,
            UploadBatch.created_rows + UploadBatch.updated_rows + UploadBatch.unchanged_rows,
            UploadBatch.rejected_rows,
        ).where(UploadBatch.created_at >= since)
    ):
        day = created_at.date().isoformat()
        daily[day][0] += accepted or 0
        daily[day][1] += rejected or 0

    total_accepted = sum(int(u[0] or 0) for u in uploads.values())
    total_rejected = sum(int(u[1] or 0) for u in uploads.values())
    return {
        "academic_year": academic_year,
        "kpis": {
            **totals,
            "institutions_total": len(institutions),
            "institutions_reporting": sum(1 for i in institutions if i["reporting"]),
            "open_findings": findings["total"],
            "high_severity_open": findings["by_severity"]["high"],
            "escalated": findings["escalated"],
            "cross_institution_flags": findings["cross_institution"],
            "acceptance_rate_pct": _pct(total_accepted, total_accepted + total_rejected),
        },
        "institutions": institutions,
        "findings_by_category": findings["by_category"],
        "findings_by_severity": findings["by_severity"],
        "upload_quality": [
            {"date": day, "accepted": acc, "rejected": rej}
            for day, (acc, rej) in sorted(daily.items())
        ],
        "counted_statuses": policy.intake_policy.count_statuses,
        "definitions": DEFINITIONS,
        "generated_at": utcnow().isoformat(),
    }
