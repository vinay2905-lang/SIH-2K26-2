import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import Principal, get_principal
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.permissions import ROLE_PERMISSIONS, Role
from app.core.ratelimit import SlidingWindowLimiter
from app.core.security import hash_token, new_token, verify_password
from app.db.base import utcnow
from app.db.session import get_db
from app.models import Institution, User, UserSession
from app.schemas.common import InstitutionRef
from app.services import audit

router = APIRouter(prefix="/auth", tags=["auth"])

_settings = get_settings()
login_limiter = SlidingWindowLimiter(_settings.login_max_attempts, _settings.login_window_seconds)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    institution: InstitutionRef | None
    permissions: list[str]


class SessionOut(BaseModel):
    user: UserOut
    csrf_token: str


def _user_out(user: User, institution: Institution | None) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        institution=InstitutionRef.model_validate(institution) if institution else None,
        permissions=sorted(p.value for p in ROLE_PERMISSIONS[Role(user.role)]),
    )


@router.post("/login", response_model=SessionOut)
def login(
    body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)
) -> SessionOut:
    settings = get_settings()
    email = body.email.strip().lower()
    if login_limiter.is_blocked(email):
        audit.record(
            db,
            action="auth.login",
            request=request,
            outcome="blocked",
            actor_email=email,
            details={"reason": "rate_limited"},
        )
        db.commit()
        raise AppError(
            429,
            "rate_limited",
            "Too many failed sign-in attempts. Please wait a few minutes and try again",
        )

    user = db.scalar(select(User).where(User.email == email))
    password_ok = verify_password(user.password_hash if user else None, body.password)
    if user is None or not password_ok or not user.is_active:
        login_limiter.hit(email)
        audit.record(
            db,
            action="auth.login",
            request=request,
            outcome="failure",
            actor_email=email,
            details={"reason": "invalid_credentials"},
        )
        db.commit()
        raise AppError(401, "invalid_credentials", "Email or password is incorrect")

    login_limiter.reset(email)
    token, csrf = new_token(), new_token()
    now = utcnow()
    session = UserSession(
        id=uuid.uuid4(),
        user_id=user.id,
        token_hash=hash_token(token),
        csrf_token=csrf,
        expires_at=now + timedelta(minutes=settings.session_ttl_minutes),
    )
    db.add(session)
    user.last_login_at = now
    audit.record(
        db,
        action="auth.login",
        request=request,
        actor_email=user.email,
        institution_id=user.institution_id,
        details={"role": user.role},
    )
    db.commit()

    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_ttl_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return SessionOut(user=_user_out(user, user.institution), csrf_token=csrf)


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    response: Response,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> Response:
    session = db.get(UserSession, principal.session_id)
    if session is not None and session.revoked_at is None:
        session.revoked_at = utcnow()
    audit.record(db, action="auth.logout", principal=principal, request=request)
    db.commit()
    response.status_code = 204
    response.delete_cookie(get_settings().session_cookie_name, path="/")
    return response


@router.get("/me", response_model=SessionOut)
def me(principal: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> SessionOut:
    user = db.get(User, principal.user_id)
    assert user is not None
    return SessionOut(user=_user_out(user, user.institution), csrf_token=principal.csrf_token)
