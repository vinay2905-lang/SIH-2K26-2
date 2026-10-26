"""Audit trail writer. Callers own the transaction; events commit with the action they record."""

import logging
import uuid
from typing import TYPE_CHECKING, Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.models import AuditEvent

if TYPE_CHECKING:
    from app.api.deps import Principal

logger = logging.getLogger("app.audit")

# Keys that must never reach the audit log, whatever the caller passes.
_FORBIDDEN_KEYS = {"password", "apaar_id", "identifier", "token", "csrf_token", "apaar"}


def _safe_details(details: dict[str, Any] | None) -> dict[str, Any]:
    if not details:
        return {}
    clean = {}
    for key, value in details.items():
        if key.lower() in _FORBIDDEN_KEYS:
            logger.warning("Dropped forbidden key %r from audit details", key)
            continue
        clean[key] = value
    return clean


def record(
    db: Session,
    *,
    action: str,
    principal: "Principal | None" = None,
    request: Request | None = None,
    target_type: str | None = None,
    target_id: uuid.UUID | str | None = None,
    institution_id: uuid.UUID | None = None,
    outcome: str = "success",
    details: dict[str, Any] | None = None,
    actor_email: str | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor_id=principal.user_id if principal else None,
        actor_email=principal.email if principal else actor_email,
        actor_role=principal.role if principal else None,
        institution_id=institution_id or (principal.institution_id if principal else None),
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        outcome=outcome,
        details=_safe_details(details),
        ip_address=request.client.host if request and request.client else None,
        request_id=getattr(request.state, "request_id", None) if request else None,
    )
    db.add(event)
    return event
