"""Authentication, CSRF and authorization dependencies shared by all routes."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError, forbidden, not_found
from app.core.permissions import Permission, has_permission, is_institution_scoped
from app.core.security import constant_time_equals, hash_token
from app.db.base import utcnow
from app.db.session import get_db
from app.models import UserSession
from app.services import audit

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
CSRF_HEADER = "X-CSRF-Token"


@dataclass(frozen=True)
class Principal:
    user_id: uuid.UUID
    email: str
    full_name: str
    role: str
    institution_id: uuid.UUID | None
    session_id: uuid.UUID
    csrf_token: str

    def can(self, permission: Permission) -> bool:
        return has_permission(self.role, permission)

    @property
    def institution_scoped(self) -> bool:
        return is_institution_scoped(self.role)

    def ensure_institution(self, institution_id: uuid.UUID, entity: str = "Resource") -> None:
        """Institution users may only touch their own institution. Responds 404, not 403, so
        that records of other institutions are not revealed to exist."""
        if self.institution_scoped and institution_id != self.institution_id:
            raise not_found(entity)


def get_principal(request: Request, db: Session = Depends(get_db)) -> Principal:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise AppError(401, "unauthenticated", "Please sign in to continue")

    session = db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(token)))
    now = utcnow()
    if session is None or session.revoked_at is not None or session.expires_at <= now:
        raise AppError(401, "session_expired", "Your session has expired. Please sign in again")
    user = session.user
    if not user.is_active:
        raise AppError(401, "account_disabled", "This account is disabled")

    if request.method not in SAFE_METHODS:
        supplied = request.headers.get(CSRF_HEADER, "")
        if not supplied or not constant_time_equals(supplied, session.csrf_token):
            raise AppError(403, "csrf_failed", "Security token missing or invalid. Reload the page")

    if now - session.last_seen_at > timedelta(minutes=1):
        session.last_seen_at = now
        db.commit()

    return Principal(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        institution_id=user.institution_id,
        session_id=session.id,
        csrf_token=session.csrf_token,
    )


def require(*permissions: Permission) -> Callable[..., Principal]:
    """Dependency factory: the caller must hold every listed permission."""

    def _dependency(
        request: Request,
        principal: Principal = Depends(get_principal),
        db: Session = Depends(get_db),
    ) -> Principal:
        missing = [p for p in permissions if not principal.can(p)]
        if missing:
            audit.record(
                db,
                action="access.denied",
                principal=principal,
                request=request,
                outcome="denied",
                details={"permission": missing[0].value, "path": request.url.path},
            )
            db.commit()
            raise forbidden()
        return principal

    return _dependency


def scoped_institution_id(principal: Principal, requested: uuid.UUID | None) -> uuid.UUID | None:
    """Institution users are pinned to their institution regardless of what they request."""
    if principal.institution_scoped:
        return principal.institution_id
    return requested
