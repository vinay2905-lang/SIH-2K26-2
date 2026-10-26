import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import Principal, require, scoped_institution_id
from app.core.errors import AppError
from app.core.permissions import Permission
from app.db.session import get_db
from app.models import AuditEvent, Institution
from app.schemas.common import Page, PageParams
from app.services import audit
from app.services.ingestion.schema import ENROLMENT_STATUSES
from app.services.settings import IDENTIFIER_PRESETS, PolicySettings, load_policy, save_setting
from app.services.validation.engine import run_validation
from app.services.validation.rules import CATEGORY_LABELS, RULES

router = APIRouter(tags=["administration"])


class AuditEventOut(BaseModel):
    id: uuid.UUID
    action: str
    outcome: str
    actor_email: str | None
    actor_role: str | None
    institution_code: str | None
    target_type: str | None
    target_id: str | None
    details: dict[str, Any]
    ip_address: str | None
    request_id: str | None
    created_at: datetime


@router.get("/audit-events", response_model=Page[AuditEventOut])
def list_audit_events(
    action: str | None = Query(None, max_length=64),
    outcome: str | None = Query(None, max_length=16),
    institution_id: uuid.UUID | None = None,
    paging: PageParams = Depends(),
    principal: Principal = Depends(require(Permission.AUDIT_READ)),
    db: Session = Depends(get_db),
) -> Page[AuditEventOut]:
    stmt = select(AuditEvent, Institution.code).outerjoin(
        Institution, AuditEvent.institution_id == Institution.id
    )
    scoped = scoped_institution_id(principal, institution_id)
    if scoped is not None:
        stmt = stmt.where(AuditEvent.institution_id == scoped)
    if action:
        stmt = stmt.where(AuditEvent.action.startswith(action, autoescape=True))
    if outcome:
        stmt = stmt.where(AuditEvent.outcome == outcome)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(
        stmt.order_by(AuditEvent.created_at.desc()).offset(paging.offset).limit(paging.page_size)
    ).all()
    return Page(
        items=[
            AuditEventOut(
                id=e.id,
                action=e.action,
                outcome=e.outcome,
                actor_email=e.actor_email,
                actor_role=e.actor_role,
                institution_code=code,
                target_type=e.target_type,
                target_id=e.target_id,
                details=e.details or {},
                ip_address=e.ip_address,
                request_id=e.request_id,
                created_at=e.created_at,
            )
            for e, code in rows
        ],
        total=total,
        page=paging.page,
        page_size=paging.page_size,
    )


def _settings_payload(policy: PolicySettings) -> dict[str, Any]:
    return {
        "policy": policy.model_dump(),
        "identifier_presets": IDENTIFIER_PRESETS,
        "rules": [
            {
                "code": r.code,
                "title": r.title,
                "category": r.category,
                "category_label": CATEGORY_LABELS[r.category],
                "severity": r.severity,
                "assumption": r.assumption,
                "enabled": policy.rules_enabled.get(r.code, True),
            }
            for r in RULES
        ],
    }


@router.get("/settings")
def get_settings_view(
    principal: Principal = Depends(require(Permission.SETTINGS_MANAGE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return _settings_payload(load_policy(db))


@router.put("/settings")
def update_settings(
    body: PolicySettings,
    request: Request,
    principal: Principal = Depends(require(Permission.SETTINGS_MANAGE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    unknown = [s for s in body.intake_policy.count_statuses if s not in ENROLMENT_STATUSES]
    if unknown:
        raise AppError(422, "validation_error", f"Unknown statuses: {', '.join(unknown)}")
    if body.consistency.min_age_at_admission >= body.consistency.max_age_at_admission:
        raise AppError(422, "validation_error", "Minimum age must be below maximum age")
    known_rules = {r.code for r in RULES}
    rules_enabled = {k: v for k, v in body.rules_enabled.items() if k in known_rules}

    before = load_policy(db)
    for key, value in (
        ("identifier_format", body.identifier_format.model_dump()),
        ("intake_policy", body.intake_policy.model_dump()),
        ("consistency", body.consistency.model_dump()),
        ("rules_enabled", rules_enabled),
    ):
        save_setting(db, key, value, principal.user_id)
    db.flush()
    after = load_policy(db)
    changed = [
        k
        for k in PolicySettings.model_fields
        if _dump(getattr(before, k)) != _dump(getattr(after, k))
    ]
    stats = run_validation(db, list(db.scalars(select(Institution.id))), policy=after)
    audit.record(
        db,
        action="settings.updated",
        principal=principal,
        request=request,
        details={
            "changed": changed,
            "findings_opened": stats.opened,
            "findings_auto_resolved": stats.auto_resolved,
        },
    )
    db.commit()
    return _settings_payload(after)


def _dump(value: Any) -> Any:
    return value.model_dump() if hasattr(value, "model_dump") else value
