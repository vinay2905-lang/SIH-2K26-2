from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import Principal, require
from app.api.v1.meta import available_academic_years
from app.core.errors import AppError
from app.core.permissions import Permission
from app.db.session import get_db
from app.models import Institution
from app.services.dashboard import central_dashboard, institution_dashboard
from app.services.ingestion.schema import academic_year_is_valid
from app.services.settings import load_policy

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def resolve_year(db: Session, requested: str | None) -> str:
    if requested:
        if not academic_year_is_valid(requested):
            raise AppError(422, "validation_error", "Academic year must look like 2025-26")
        return requested
    years = available_academic_years(db)
    if not years:
        raise AppError(404, "not_found", "No academic years are configured yet")
    return years[0]


@router.get("/institution")
def get_institution_dashboard(
    academic_year: str | None = Query(None, max_length=7),
    principal: Principal = Depends(require(Permission.DASHBOARD_INSTITUTION)),
    db: Session = Depends(get_db),
) -> dict:
    institution = db.get(Institution, principal.institution_id)
    if institution is None:
        raise AppError(403, "forbidden", "No institution is linked to this account")
    return institution_dashboard(db, load_policy(db), institution, resolve_year(db, academic_year))


@router.get("/central")
def get_central_dashboard(
    academic_year: str | None = Query(None, max_length=7),
    principal: Principal = Depends(require(Permission.DASHBOARD_CENTRAL)),
    db: Session = Depends(get_db),
) -> dict:
    return central_dashboard(db, load_policy(db), resolve_year(db, academic_year))
