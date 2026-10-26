import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import Principal, require, scoped_institution_id
from app.core.errors import AppError, not_found
from app.core.permissions import Permission
from app.db.base import utcnow
from app.db.session import get_db
from app.models import Finding, ReviewAction
from app.models.finding import ACTIVE_STATUSES, CLOSED_STATUSES, FINDING_STATUSES
from app.schemas.common import InstitutionRef, Page, PageParams, ProgrammeRef
from app.services import audit
from app.services.validation.rules import CATEGORY_LABELS, RULES_BY_CODE

router = APIRouter(tags=["findings"])

ACTIONS_NEEDING_COMMENT = {"resolve", "dismiss", "escalate", "reopen", "comment"}
TRANSITIONS = {
    "start_review": "in_review",
    "resolve": "resolved",
    "dismiss": "dismissed",
    "escalate": "escalated",
    "reopen": "open",
}
SEVERITY_RANK = case({"high": 0, "medium": 1, "low": 2}, value=Finding.severity, else_=3)


class StudentBrief(BaseModel):
    id: uuid.UUID
    institution_student_id: str
    full_name: str


class FindingOut(BaseModel):
    id: uuid.UUID
    rule_code: str
    category: str
    category_label: str
    severity: str
    status: str
    title: str
    reason: str
    institution: InstitutionRef
    student: StudentBrief | None
    programme: ProgrammeRef | None
    academic_year: str | None
    created_at: datetime
    updated_at: datetime


class ReviewActionOut(BaseModel):
    action: str
    from_status: str | None
    to_status: str | None
    comment: str | None
    actor_name: str
    created_at: datetime


class RuleInfo(BaseModel):
    checks: str
    rationale: str
    assumption: str | None
    central_resolution: bool


class FindingDetail(FindingOut):
    evidence: list[dict[str, Any]]
    restricted_evidence: list[dict[str, Any]] | None
    restricted_evidence_hidden: bool
    recommended_action: str
    rule: RuleInfo | None
    history: list[ReviewActionOut]
    allowed_actions: list[str]
    source_batch_id: uuid.UUID | None
    resolved_at: datetime | None


class ActionIn(BaseModel):
    action: Literal["start_review", "resolve", "dismiss", "escalate", "reopen", "comment"]
    comment: str | None = Field(default=None, max_length=1000)


def _out(f: Finding) -> FindingOut:
    return FindingOut(
        id=f.id,
        rule_code=f.rule_code,
        category=f.category,
        category_label=CATEGORY_LABELS.get(f.category, f.category),
        severity=f.severity,
        status=f.status,
        title=f.title,
        reason=f.reason,
        institution=InstitutionRef.model_validate(f.institution),
        student=StudentBrief(
            id=f.student.id,
            institution_student_id=f.student.institution_student_id,
            full_name=f.student.full_name,
        )
        if f.student
        else None,
        programme=ProgrammeRef.model_validate(f.programme) if f.programme else None,
        academic_year=f.academic_year,
        created_at=f.created_at,
        updated_at=f.updated_at,
    )


def allowed_actions(principal: Principal, finding: Finding) -> list[str]:
    if not principal.can(Permission.FINDINGS_REVIEW):
        return []
    central = not principal.institution_scoped
    spec = RULES_BY_CODE.get(finding.rule_code)
    central_only = bool(spec and spec.central_resolution)
    status = finding.status
    actions = ["comment"]
    if status == "open":
        actions.append("start_review")
    if status in ("open", "in_review"):
        if central or not central_only:
            actions += ["resolve", "dismiss"]
        if not central:
            actions.append("escalate")
    if status == "escalated" and central:
        actions += ["resolve", "dismiss"]
    if status in CLOSED_STATUSES and (central or not central_only):
        actions.append("reopen")
    return actions


def _detail(principal: Principal, f: Finding) -> FindingDetail:
    spec = RULES_BY_CODE.get(f.rule_code)
    central = not principal.institution_scoped
    has_restricted = bool(f.restricted_evidence)
    return FindingDetail(
        **_out(f).model_dump(),
        evidence=(f.evidence or {}).get("facts", []),
        restricted_evidence=(f.restricted_evidence or {}).get("facts", [])
        if central and has_restricted
        else None,
        restricted_evidence_hidden=has_restricted and not central,
        recommended_action=f.recommended_action,
        rule=RuleInfo(
            checks=spec.checks,
            rationale=spec.rationale,
            assumption=spec.assumption,
            central_resolution=spec.central_resolution,
        )
        if spec
        else None,
        history=[
            ReviewActionOut(
                action=a.action,
                from_status=a.from_status,
                to_status=a.to_status,
                comment=a.comment,
                actor_name=a.actor.full_name if a.actor else "System",
                created_at=a.created_at,
            )
            for a in f.actions
        ],
        allowed_actions=allowed_actions(principal, f),
        source_batch_id=f.source_batch_id,
        resolved_at=f.resolved_at,
    )


def _get(db: Session, principal: Principal, finding_id: uuid.UUID) -> Finding:
    finding = db.get(Finding, finding_id)
    if finding is None:
        raise not_found("Finding")
    principal.ensure_institution(finding.institution_id, "Finding")
    return finding


def _scoped(principal: Principal, institution_id: uuid.UUID | None):  # noqa: ANN202
    stmt = select(Finding)
    scoped = scoped_institution_id(principal, institution_id)
    if scoped is not None:
        stmt = stmt.where(Finding.institution_id == scoped)
    return stmt


@router.get("/findings", response_model=Page[FindingOut])
def list_findings(
    status: str = Query("active", max_length=16),
    category: str | None = Query(None, max_length=32),
    severity: str | None = Query(None, max_length=8),
    rule_code: str | None = Query(None, max_length=64),
    academic_year: str | None = Query(None, max_length=7),
    institution_id: uuid.UUID | None = None,
    student_id: uuid.UUID | None = None,
    batch_id: uuid.UUID | None = None,
    paging: PageParams = Depends(),
    principal: Principal = Depends(require(Permission.FINDINGS_READ)),
    db: Session = Depends(get_db),
) -> Page[FindingOut]:
    stmt = _scoped(principal, institution_id)
    if status == "active":
        stmt = stmt.where(Finding.status.in_(ACTIVE_STATUSES))
    elif status == "closed":
        stmt = stmt.where(Finding.status.in_(CLOSED_STATUSES))
    elif status in FINDING_STATUSES:
        stmt = stmt.where(Finding.status == status)
    elif status != "all":
        raise AppError(422, "validation_error", "Unknown status filter")
    if category:
        stmt = stmt.where(Finding.category == category)
    if severity:
        stmt = stmt.where(Finding.severity == severity)
    if rule_code:
        stmt = stmt.where(Finding.rule_code == rule_code)
    if academic_year:
        stmt = stmt.where(Finding.academic_year == academic_year)
    if student_id:
        stmt = stmt.where(Finding.student_id == student_id)
    if batch_id:
        stmt = stmt.where(Finding.source_batch_id == batch_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    findings = db.scalars(
        stmt.options(
            selectinload(Finding.institution),
            selectinload(Finding.student),
            selectinload(Finding.programme),
        )
        .order_by(SEVERITY_RANK, Finding.created_at.desc(), Finding.id)
        .offset(paging.offset)
        .limit(paging.page_size)
    ).all()
    return Page(
        items=[_out(f) for f in findings], total=total, page=paging.page, page_size=paging.page_size
    )


@router.get("/findings/summary")
def findings_summary(
    institution_id: uuid.UUID | None = None,
    principal: Principal = Depends(require(Permission.FINDINGS_READ)),
    db: Session = Depends(get_db),
) -> dict:
    stmt = _scoped(principal, institution_id).subquery()
    by_status = dict(db.execute(select(stmt.c.status, func.count()).group_by(stmt.c.status)).all())
    active = select(stmt).where(stmt.c.status.in_(ACTIVE_STATUSES)).subquery()
    by_category = dict(
        db.execute(select(active.c.category, func.count()).group_by(active.c.category)).all()
    )
    by_severity = dict(
        db.execute(select(active.c.severity, func.count()).group_by(active.c.severity)).all()
    )
    return {
        "by_status": {s: by_status.get(s, 0) for s in FINDING_STATUSES},
        "active_by_category": [
            {"category": c, "label": label, "count": by_category.get(c, 0)}
            for c, label in CATEGORY_LABELS.items()
        ],
        "active_by_severity": {s: by_severity.get(s, 0) for s in ("high", "medium", "low")},
        "active_total": sum(by_status.get(s, 0) for s in ACTIVE_STATUSES),
    }


@router.get("/findings/{finding_id}", response_model=FindingDetail)
def get_finding(
    finding_id: uuid.UUID,
    principal: Principal = Depends(require(Permission.FINDINGS_READ)),
    db: Session = Depends(get_db),
) -> FindingDetail:
    return _detail(principal, _get(db, principal, finding_id))


@router.post("/findings/{finding_id}/actions", response_model=FindingDetail)
def act_on_finding(
    finding_id: uuid.UUID,
    body: ActionIn,
    request: Request,
    principal: Principal = Depends(require(Permission.FINDINGS_REVIEW)),
    db: Session = Depends(get_db),
) -> FindingDetail:
    finding = _get(db, principal, finding_id)
    if body.action not in allowed_actions(principal, finding):
        raise AppError(
            409,
            "action_not_allowed",
            f"'{body.action}' is not available for this finding in its current state "
            f"or for your role",
        )
    comment = (body.comment or "").strip() or None
    if body.action in ACTIONS_NEEDING_COMMENT and (comment is None or len(comment) < 5):
        raise AppError(422, "comment_required", "Add a short comment (at least 5 characters)")

    previous = finding.status
    new_status = TRANSITIONS.get(body.action, previous)
    finding.status = new_status
    if new_status in CLOSED_STATUSES:
        finding.resolved_at = utcnow()
        finding.resolved_by_id = principal.user_id
    elif body.action == "reopen":
        finding.resolved_at = None
        finding.resolved_by_id = None
    db.add(
        ReviewAction(
            finding_id=finding.id,
            actor_id=principal.user_id,
            action=body.action,
            from_status=previous,
            to_status=new_status,
            comment=comment,
        )
    )
    audit.record(
        db,
        action=f"finding.{body.action}",
        principal=principal,
        request=request,
        target_type="finding",
        target_id=finding.id,
        institution_id=finding.institution_id,
        details={"rule_code": finding.rule_code, "from": previous, "to": new_status},
    )
    db.commit()
    db.refresh(finding)
    return _detail(principal, finding)
