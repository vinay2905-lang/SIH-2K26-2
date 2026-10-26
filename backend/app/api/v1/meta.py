from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import Principal, get_principal
from app.core.config import get_settings
from app.db.session import get_db
from app.models import IntakeConfiguration
from app.services.ingestion.schema import COLUMNS, ENROLMENT_STATUSES, GENDERS, SEAT_TYPES
from app.services.settings import load_policy
from app.services.validation.rules import CATEGORY_LABELS, RULES
from app.services.verification.adapter import get_provider

router = APIRouter(tags=["meta"])


def available_academic_years(db: Session) -> list[str]:
    years = db.scalars(select(IntakeConfiguration.academic_year).distinct()).all()
    return sorted(years, reverse=True)


@router.get("/meta/config")
def config(principal: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    policy = load_policy(db)
    provider = get_provider()
    return {
        "identifier_format": {
            "label": policy.identifier_format.label,
            "example": policy.identifier_format.example,
        },
        "columns": [
            {
                "name": c.name,
                "required": c.required,
                "description": c.description,
                "example": c.example,
            }
            for c in COLUMNS
        ],
        "seat_types": list(SEAT_TYPES),
        "enrolment_statuses": list(ENROLMENT_STATUSES),
        "genders": list(GENDERS),
        "counted_statuses": policy.intake_policy.count_statuses,
        "academic_years": available_academic_years(db),
        "verification_provider": {"name": provider.display_name, "simulated": provider.simulated},
        "demo_mode": settings.is_demo,
        "upload_limits": {
            "max_bytes": settings.upload_max_bytes,
            "max_rows": settings.upload_max_rows,
        },
        "finding_categories": CATEGORY_LABELS,
    }


@router.get("/rules")
def rules(principal: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> list:
    policy = load_policy(db)
    return [
        {
            "code": r.code,
            "category": r.category,
            "category_label": CATEGORY_LABELS[r.category],
            "severity": r.severity,
            "title": r.title,
            "checks": r.checks,
            "rationale": r.rationale,
            "recommended_action": r.recommended_action,
            "assumption": r.assumption,
            "central_resolution": r.central_resolution,
            "enabled": policy.rules_enabled.get(r.code, True),
        }
        for r in RULES
    ]
