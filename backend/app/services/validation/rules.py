"""Deterministic, explainable validation rules.

Each rule states what it checks, why it matters, what a reviewer can do, and which policy
assumption (if any) it relies on. Each finding carries the specific facts that triggered it.
Findings are review signals; none of them is a determination of fraud or misconduct.
"""

import uuid
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date
from functools import cached_property
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.identifiers import mask
from app.models import Admission, Institution, IntakeConfiguration, Programme, Student
from app.services.settings import PolicySettings

CATEGORY_LABELS = {
    "INTAKE": "Intake compliance",
    "DUPLICATE": "Potential duplicate",
    "CROSS_INSTITUTION": "Cross-institution match",
    "CONSISTENCY": "Data consistency",
}


@dataclass
class FindingDraft:
    rule_code: str
    institution_id: uuid.UUID
    dedupe_key: str
    reason: str
    facts: list[dict[str, Any]]
    target_type: str
    metrics: dict[str, Any] = field(default_factory=dict)
    restricted_facts: list[dict[str, Any]] = field(default_factory=list)
    student_id: uuid.UUID | None = None
    admission_id: uuid.UUID | None = None
    programme_id: uuid.UUID | None = None
    academic_year: str | None = None

    @property
    def evidence(self) -> dict[str, Any]:
        return {"facts": self.facts, "metrics": self.metrics}

    @property
    def restricted_evidence(self) -> dict[str, Any]:
        return {"facts": self.restricted_facts} if self.restricted_facts else {}


@dataclass(frozen=True)
class AdmissionView:
    admission_id: uuid.UUID
    student_id: uuid.UUID
    institution_id: uuid.UUID
    programme_id: uuid.UUID
    programme_code: str
    programme_name: str
    academic_year: str
    admission_date: date
    seat_type: str
    nri: bool
    oci: bool
    fn: bool
    enrolment_status: str
    institution_student_id: str
    apaar_last4: str
    date_of_birth: date
    nationality: str

    @property
    def student_ref(self) -> str:
        return f"{self.institution_student_id} (APAAR {mask(self.apaar_last4)})"

    @property
    def programme_label(self) -> str:
        return f"{self.programme_name} ({self.programme_code})"


@dataclass
class RuleContext:
    institution: Institution
    policy: PolicySettings
    admissions: list[AdmissionView]
    intake: dict[tuple[uuid.UUID, str], IntakeConfiguration]
    programmes: dict[uuid.UUID, Programme]

    @property
    def counted_statuses(self) -> list[str]:
        return self.policy.intake_policy.count_statuses

    def is_counted(self, a: AdmissionView) -> bool:
        return a.enrolment_status in self.counted_statuses

    @cached_property
    def seat_counts(self) -> dict[tuple[uuid.UUID, str], Counter[str]]:
        counts: dict[tuple[uuid.UUID, str], Counter[str]] = defaultdict(Counter)
        for a in self.admissions:
            if self.is_counted(a):
                counts[(a.programme_id, a.academic_year)][a.seat_type] += 1
        return counts

    def programme_label(self, programme_id: uuid.UUID) -> str:
        p = self.programmes[programme_id]
        return f"{p.name} ({p.code})"


def load_context(db: Session, institution: Institution, policy: PolicySettings) -> RuleContext:
    rows = db.execute(
        select(Admission, Student, Programme)
        .join(Student, Admission.student_id == Student.id)
        .join(Programme, Admission.programme_id == Programme.id)
        .where(Admission.institution_id == institution.id)
    ).all()
    admissions = [
        AdmissionView(
            admission_id=a.id,
            student_id=s.id,
            institution_id=a.institution_id,
            programme_id=p.id,
            programme_code=p.code,
            programme_name=p.name,
            academic_year=a.academic_year,
            admission_date=a.admission_date,
            seat_type=a.seat_type,
            nri=a.nri_category,
            oci=a.oci_status,
            fn=a.foreign_national_status,
            enrolment_status=a.enrolment_status,
            institution_student_id=s.institution_student_id,
            apaar_last4=s.apaar_last4,
            date_of_birth=s.date_of_birth,
            nationality=s.nationality,
        )
        for a, s, p in rows
    ]
    programmes = {
        p.id: p
        for p in db.scalars(select(Programme).where(Programme.institution_id == institution.id))
    }
    intake = (
        {
            (c.programme_id, c.academic_year): c
            for c in db.scalars(
                select(IntakeConfiguration).where(
                    IntakeConfiguration.programme_id.in_(programmes.keys())
                )
            )
        }
        if programmes
        else {}
    )
    return RuleContext(institution, policy, admissions, intake, programmes)


def _fact(label: str, value: Any) -> dict[str, Any]:
    return {"label": label, "value": value}


# --- Intake rules -------------------------------------------------------------------------


def _intake_exceeded(ctx: RuleContext) -> Iterable[FindingDraft]:
    statuses = ", ".join(ctx.counted_statuses)
    for (programme_id, year), counts in ctx.seat_counts.items():
        config = ctx.intake.get((programme_id, year))
        if config is None:
            continue
        counted = counts.get("REGULAR", 0)
        if counted <= config.approved_intake:
            continue
        excess = counted - config.approved_intake
        label = ctx.programme_label(programme_id)
        yield FindingDraft(
            rule_code="INTAKE_EXCEEDED",
            institution_id=ctx.institution.id,
            dedupe_key=f"INTAKE_EXCEEDED:{programme_id}:{year}",
            reason=(
                f"{label} has {counted} regular-seat admissions with status {statuses} in "
                f"{year}, exceeding the approved intake of {config.approved_intake} by {excess}."
            ),
            facts=[
                _fact("Programme", label),
                _fact("Academic year", year),
                _fact("Regular-seat admissions counted", counted),
                _fact("Approved intake (configured)", config.approved_intake),
                _fact("Excess", excess),
                _fact("Statuses counted", statuses),
                _fact("Intake figure source", config.source),
            ],
            metrics={"counted": counted, "limit": config.approved_intake, "excess": excess},
            target_type="programme_intake",
            programme_id=programme_id,
            academic_year=year,
        )


def _supernumerary_exceeded(ctx: RuleContext) -> Iterable[FindingDraft]:
    statuses = ", ".join(ctx.counted_statuses)
    for (programme_id, year), counts in ctx.seat_counts.items():
        config = ctx.intake.get((programme_id, year))
        if config is None:
            continue
        counted = counts.get("SUPERNUMERARY", 0)
        if counted <= config.supernumerary_seats:
            continue
        excess = counted - config.supernumerary_seats
        label = ctx.programme_label(programme_id)
        yield FindingDraft(
            rule_code="SUPERNUMERARY_EXCEEDED",
            institution_id=ctx.institution.id,
            dedupe_key=f"SUPERNUMERARY_EXCEEDED:{programme_id}:{year}",
            reason=(
                f"{label} has {counted} supernumerary-seat admissions in {year}, but only "
                f"{config.supernumerary_seats} supernumerary seats are configured."
            ),
            facts=[
                _fact("Programme", label),
                _fact("Academic year", year),
                _fact("Supernumerary admissions counted", counted),
                _fact("Supernumerary seats (configured)", config.supernumerary_seats),
                _fact("Excess", excess),
                _fact("Statuses counted", statuses),
            ],
            metrics={"counted": counted, "limit": config.supernumerary_seats, "excess": excess},
            target_type="programme_intake",
            programme_id=programme_id,
            academic_year=year,
        )


def _intake_not_configured(ctx: RuleContext) -> Iterable[FindingDraft]:
    for (programme_id, year), counts in ctx.seat_counts.items():
        if (programme_id, year) in ctx.intake:
            continue
        total = sum(counts.values())
        label = ctx.programme_label(programme_id)
        yield FindingDraft(
            rule_code="INTAKE_NOT_CONFIGURED",
            institution_id=ctx.institution.id,
            dedupe_key=f"INTAKE_NOT_CONFIGURED:{programme_id}:{year}",
            reason=(
                f"{label} has {total} counted admissions in {year}, but no approved intake is "
                f"configured for that programme and year, so intake compliance cannot be checked."
            ),
            facts=[
                _fact("Programme", label),
                _fact("Academic year", year),
                _fact("Admissions counted", total),
                _fact("Approved intake", "Not configured"),
            ],
            metrics={"counted": total},
            target_type="programme_intake",
            programme_id=programme_id,
            academic_year=year,
        )


# --- Duplicate rules ----------------------------------------------------------------------


def _multiple_active_admissions(ctx: RuleContext) -> Iterable[FindingDraft]:
    groups: dict[tuple[uuid.UUID, str], list[AdmissionView]] = defaultdict(list)
    for a in ctx.admissions:
        if ctx.is_counted(a):
            groups[(a.student_id, a.academic_year)].append(a)
    for (student_id, year), items in groups.items():
        if len(items) < 2:
            continue
        programmes = sorted(a.programme_code for a in items)
        yield FindingDraft(
            rule_code="MULTIPLE_ACTIVE_ADMISSIONS",
            institution_id=ctx.institution.id,
            dedupe_key=f"MULTIPLE_ACTIVE_ADMISSIONS:{student_id}:{year}",
            reason=(
                f"Student {items[0].student_ref} has {len(items)} active admissions in {year} "
                f"({', '.join(programmes)}) at this institution."
            ),
            facts=[
                _fact("Student", items[0].student_ref),
                _fact("Academic year", year),
                _fact("Programmes with an active admission", ", ".join(programmes)),
            ],
            metrics={"admissions": len(items)},
            target_type="student",
            student_id=student_id,
            academic_year=year,
        )


def evaluate_cross_institution(db: Session, policy: PolicySettings) -> list[FindingDraft]:
    """Same identifier fingerprint with a counted admission at 2+ institutions in one year."""
    statuses = policy.intake_policy.count_statuses
    groups = db.execute(
        select(Student.apaar_fingerprint, Admission.academic_year)
        .join(Admission, Admission.student_id == Student.id)
        .where(Admission.enrolment_status.in_(statuses))
        .group_by(Student.apaar_fingerprint, Admission.academic_year)
        .having(func.count(func.distinct(Admission.institution_id)) > 1)
    ).all()
    if not groups:
        return []

    fingerprints = {g[0] for g in groups}
    wanted = {(g[0], g[1]) for g in groups}
    rows = db.execute(
        select(Student, Admission, Programme, Institution)
        .join(Admission, Admission.student_id == Student.id)
        .join(Programme, Admission.programme_id == Programme.id)
        .join(Institution, Admission.institution_id == Institution.id)
        .where(Student.apaar_fingerprint.in_(fingerprints))
        .where(Admission.enrolment_status.in_(statuses))
    ).all()

    by_group: dict[tuple[str, str], list[tuple[Student, Admission, Programme, Institution]]] = (
        defaultdict(list)
    )
    for row in rows:
        key = (row[0].apaar_fingerprint, row[1].academic_year)
        if key in wanted:
            by_group[key].append(row)

    drafts = []
    for (_, year), members in by_group.items():
        involved = sorted(
            {f"{inst.code} — {inst.name} ({prog.code})" for _, _, prog, inst in members}
        )
        institution_ids = {inst.id for _, _, _, inst in members}
        seen_students: set[uuid.UUID] = set()
        for student, _, _, inst in members:
            if student.id in seen_students:
                continue
            seen_students.add(student.id)
            others = len(institution_ids) - 1
            ref = f"{student.institution_student_id} (APAAR {mask(student.apaar_last4)})"
            drafts.append(
                FindingDraft(
                    rule_code="CROSS_INSTITUTION_DUPLICATE",
                    institution_id=inst.id,
                    dedupe_key=f"CROSS_INSTITUTION_DUPLICATE:{student.id}:{year}",
                    reason=(
                        f"Student {ref} also has an active admission in {year} at {others} other "
                        f"institution(s). This can be legitimate (for example a permitted dual "
                        f"programme or a mid-year transfer) and needs review; it is not a finding "
                        f"of wrongdoing."
                    ),
                    facts=[
                        _fact("Student", ref),
                        _fact("Academic year", year),
                        _fact("Other institutions with an active admission", others),
                        _fact("Match basis", "Identical APAAR ID (keyed fingerprint match)"),
                    ],
                    metrics={"institutions": len(institution_ids)},
                    restricted_facts=[_fact("Institutions involved", "; ".join(involved))],
                    target_type="student",
                    student_id=student.id,
                    academic_year=year,
                )
            )
    return drafts


# --- Consistency rules --------------------------------------------------------------------


def _category_conflicts(a: AdmissionView) -> list[str]:
    conflicts = []
    if a.nri and a.fn:
        conflicts.append("Marked as both NRI and Foreign National")
    if a.nri and a.oci:
        conflicts.append("Marked as both NRI and OCI")
    if a.fn and a.nationality == "IN":
        conflicts.append("Foreign National status with Indian nationality (IN)")
    if a.oci and a.nationality == "IN":
        conflicts.append("OCI status with Indian nationality (IN)")
    if a.nri and a.nationality != "IN":
        conflicts.append(f"NRI category with non-Indian nationality ({a.nationality})")
    return conflicts


def _category_conflict(ctx: RuleContext) -> Iterable[FindingDraft]:
    for a in ctx.admissions:
        conflicts = _category_conflicts(a)
        if not conflicts:
            continue
        yield FindingDraft(
            rule_code="CATEGORY_CONFLICT",
            institution_id=ctx.institution.id,
            dedupe_key=f"CATEGORY_CONFLICT:{a.admission_id}",
            reason=f"Admission of {a.student_ref} to {a.programme_code} ({a.academic_year}) has "
            f"conflicting category fields: {'; '.join(conflicts)}.",
            facts=[
                _fact("Student", a.student_ref),
                _fact("Programme", a.programme_label),
                _fact("Academic year", a.academic_year),
                _fact("NRI / OCI / FN", f"{_yn(a.nri)} / {_yn(a.oci)} / {_yn(a.fn)}"),
                _fact("Nationality", a.nationality),
                _fact("Conflicts", "; ".join(conflicts)),
            ],
            target_type="admission",
            student_id=a.student_id,
            admission_id=a.admission_id,
            programme_id=a.programme_id,
            academic_year=a.academic_year,
        )


def _yn(value: bool) -> str:
    return "Y" if value else "N"


def _age_on(birth: date, on: date) -> int:
    return on.year - birth.year - ((on.month, on.day) < (birth.month, birth.day))


def _age_at_admission(ctx: RuleContext) -> Iterable[FindingDraft]:
    lo = ctx.policy.consistency.min_age_at_admission
    hi = ctx.policy.consistency.max_age_at_admission
    for a in ctx.admissions:
        age = _age_on(a.date_of_birth, a.admission_date)
        if lo <= age <= hi:
            continue
        yield FindingDraft(
            rule_code="AGE_AT_ADMISSION",
            institution_id=ctx.institution.id,
            dedupe_key=f"AGE_AT_ADMISSION:{a.admission_id}",
            reason=f"{a.student_ref} would be {age} years old on the admission date, outside the "
            f"configured plausible range of {lo}–{hi}. The date of birth or admission date may be "
            f"mistyped.",
            facts=[
                _fact("Student", a.student_ref),
                _fact("Programme", a.programme_label),
                _fact("Age on admission date", age),
                _fact("Configured range", f"{lo}–{hi}"),
            ],
            metrics={"age": age},
            target_type="admission",
            student_id=a.student_id,
            admission_id=a.admission_id,
            programme_id=a.programme_id,
            academic_year=a.academic_year,
        )


def academic_year_window(year: str, start_month: int) -> tuple[date, date]:
    start_year = int(year[:4])
    start = date(start_year, start_month, 1)
    end_year, end_month = (start_year + 1, start_month - 1) if start_month > 1 else (start_year, 12)
    following = date(end_year + (end_month == 12), end_month % 12 + 1, 1)
    return start, date.fromordinal(following.toordinal() - 1)


def _admission_date_outside_year(ctx: RuleContext) -> Iterable[FindingDraft]:
    start_month = ctx.policy.consistency.academic_year_start_month
    for a in ctx.admissions:
        start, end = academic_year_window(a.academic_year, start_month)
        if start <= a.admission_date <= end:
            continue
        yield FindingDraft(
            rule_code="ADMISSION_DATE_OUTSIDE_YEAR",
            institution_id=ctx.institution.id,
            dedupe_key=f"ADMISSION_DATE_OUTSIDE_YEAR:{a.admission_id}",
            reason=f"Admission date {a.admission_date.isoformat()} for {a.student_ref} falls "
            f"outside the configured window for {a.academic_year} "
            f"({start.isoformat()} to {end.isoformat()}).",
            facts=[
                _fact("Student", a.student_ref),
                _fact("Programme", a.programme_label),
                _fact("Admission date", a.admission_date.isoformat()),
                _fact("Academic year window", f"{start.isoformat()} to {end.isoformat()}"),
            ],
            target_type="admission",
            student_id=a.student_id,
            admission_id=a.admission_id,
            programme_id=a.programme_id,
            academic_year=a.academic_year,
        )


@dataclass(frozen=True)
class RuleSpec:
    code: str
    category: str
    severity: str
    title: str
    checks: str
    rationale: str
    recommended_action: str
    scope: str  # "institution" or "global"
    central_resolution: bool
    assumption: str | None
    evaluate: Callable[[RuleContext], Iterable[FindingDraft]] | None = None


INTAKE_ASSUMPTION = (
    "Regular-seat admissions are counted against approved intake and supernumerary-seat "
    "admissions against configured supernumerary seats, using the seat type declared by the "
    "institution and the configured counted statuses. Pending authoritative confirmation."
)

RULES: tuple[RuleSpec, ...] = (
    RuleSpec(
        code="INTAKE_EXCEEDED",
        category="INTAKE",
        severity="high",
        title="Admissions exceed approved intake",
        checks="Counted regular-seat admissions per programme and year versus approved intake.",
        rationale="Admissions beyond approved intake may breach approval conditions.",
        recommended_action="Confirm the admission list and seat types. If correct, record the "
        "approval reference or escalate to the regulator; if not, correct the records.",
        scope="institution",
        central_resolution=True,
        assumption=INTAKE_ASSUMPTION,
        evaluate=_intake_exceeded,
    ),
    RuleSpec(
        code="SUPERNUMERARY_EXCEEDED",
        category="INTAKE",
        severity="high",
        title="Supernumerary admissions exceed configured seats",
        checks="Counted supernumerary-seat admissions versus configured supernumerary seats.",
        rationale="Supernumerary seats are limited; excess use may indicate misclassification.",
        recommended_action="Check each supernumerary admission's seat type and sanction.",
        scope="institution",
        central_resolution=True,
        assumption=INTAKE_ASSUMPTION,
        evaluate=_supernumerary_exceeded,
    ),
    RuleSpec(
        code="INTAKE_NOT_CONFIGURED",
        category="INTAKE",
        severity="high",
        title="No approved intake configured",
        checks="Programme-years that have admissions but no approved intake configuration.",
        rationale="Without an approved intake figure, compliance cannot be assessed.",
        recommended_action="Ask the central team to configure the approved intake, or check the "
        "programme code and academic year on the records.",
        scope="institution",
        central_resolution=True,
        assumption=None,
        evaluate=_intake_not_configured,
    ),
    RuleSpec(
        code="MULTIPLE_ACTIVE_ADMISSIONS",
        category="DUPLICATE",
        severity="medium",
        title="Multiple active admissions in one year",
        checks="A student with more than one counted admission in the same academic year at the "
        "same institution.",
        rationale="Often a duplicate entry under a second programme; occasionally legitimate.",
        recommended_action="Cancel the duplicate admission, or dismiss with a note if both "
        "programmes are genuinely being pursued.",
        scope="institution",
        central_resolution=False,
        assumption=None,
        evaluate=_multiple_active_admissions,
    ),
    RuleSpec(
        code="CROSS_INSTITUTION_DUPLICATE",
        category="CROSS_INSTITUTION",
        severity="high",
        title="Potential duplicate enrolment across institutions",
        checks="The same APAAR ID (matched by keyed fingerprint) with a counted admission at two "
        "or more institutions in the same academic year.",
        rationale="May indicate a seat held at more than one institution, a transfer not yet "
        "recorded, or a data-entry error. It can also be legitimate.",
        recommended_action="Institution: confirm the student's status and comment or escalate. "
        "Central reviewer: compare records across institutions and resolve.",
        scope="global",
        central_resolution=True,
        assumption=None,
    ),
    RuleSpec(
        code="CATEGORY_CONFLICT",
        category="CONSISTENCY",
        severity="medium",
        title="Conflicting NRI / OCI / FN / nationality fields",
        checks="Combinations such as NRI with Foreign National, or FN with Indian nationality.",
        rationale="Category fields drive intake treatment and reporting, so conflicts distort "
        "both.",
        recommended_action="Correct the category fields, or dismiss with an explanation.",
        scope="institution",
        central_resolution=False,
        assumption="Uses general definitions (an NRI is an Indian citizen; OCI and FN holders "
        "are not). Pending authoritative confirmation; can be switched off.",
        evaluate=_category_conflict,
    ),
    RuleSpec(
        code="AGE_AT_ADMISSION",
        category="CONSISTENCY",
        severity="low",
        title="Implausible age at admission",
        checks="Age on the admission date outside the configured plausible range.",
        rationale="Usually a mistyped date of birth or admission date.",
        recommended_action="Check the dates against source documents and correct them.",
        scope="institution",
        central_resolution=False,
        assumption="Plausible range is configurable (default 15–60).",
        evaluate=_age_at_admission,
    ),
    RuleSpec(
        code="ADMISSION_DATE_OUTSIDE_YEAR",
        category="CONSISTENCY",
        severity="low",
        title="Admission date outside the academic year",
        checks="Admission date outside the configured academic-year window.",
        rationale="Usually the wrong academic year or a mistyped date.",
        recommended_action="Correct the academic year or the admission date.",
        scope="institution",
        central_resolution=False,
        assumption="Academic year window starts on a configurable month (default April).",
        evaluate=_admission_date_outside_year,
    ),
)

RULES_BY_CODE = {r.code: r for r in RULES}
