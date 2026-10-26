"""Endpoints that exist only to make the local demo easy. Disabled when APP_ENV=production."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import Principal, require
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.permissions import Permission
from app.db.session import get_db
from app.models import Institution, User
from app.seed import DEMO_PASSWORD, demo_upload_rows
from app.services import audit

router = APIRouter(tags=["demo"])

ROLE_DESCRIPTIONS = {
    "institution_operator": "Uploads and maintains the institution's student records",
    "institution_admin": "Reviews findings, issues records and sees the institution audit trail",
    "central_reviewer": "Monitors all institutions and resolves escalated findings",
    "authorized_verifier": "Verifies records with the student's consent (minimum data)",
    "system_admin": "Configures validation policy and approved intake",
}


def _demo_mode() -> bool:
    return get_settings().app_env != "production"


@router.get("/meta/public")
def public_meta(db: Session = Depends(get_db)) -> dict:
    """Unauthenticated: app identity and, in demo mode only, the synthetic demo accounts."""
    accounts = []
    if _demo_mode():
        rows = db.execute(
            select(User, Institution.name)
            .outerjoin(Institution, User.institution_id == Institution.id)
            .where(User.email.endswith("@demo.example"), User.is_active.is_(True))
            .order_by(User.email)
        ).all()
        accounts = [
            {
                "email": u.email,
                "role": u.role,
                "institution": inst,
                "description": ROLE_DESCRIPTIONS.get(u.role, ""),
            }
            for u, inst in rows
        ]
    return {
        "app_name": "APAAR Student Data Platform",
        "problem_statement": "SIH26263",
        "demo_mode": _demo_mode(),
        "demo_accounts": accounts,
        "demo_password": DEMO_PASSWORD if accounts else None,
    }


@router.get("/demo/sample-upload.csv")
def sample_upload(
    request: Request,
    principal: Principal = Depends(require(Permission.UPLOADS_CREATE)),
    db: Session = Depends(get_db),
) -> Response:
    if not _demo_mode():
        raise AppError(404, "not_found", "Not found")
    institution = db.get(Institution, principal.institution_id)
    if institution is None:
        raise AppError(403, "forbidden", "No institution is linked to this account")
    audit.record(db, action="demo.sample_downloaded", principal=principal, request=request)
    db.commit()
    return Response(
        content=demo_upload_rows(db, institution),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="demo-upload-{institution.code}.csv"',
            "Cache-Control": "no-store",
        },
    )
