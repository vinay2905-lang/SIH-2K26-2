"""Configurable policy. Every value here is a documented prototype assumption, not an official
rule; see docs/assumptions-and-open-questions.md. Values are stored in ``system_settings`` and
fall back to these defaults."""

import copy
import re
from typing import Any

from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.models import SystemSetting

DEMO_IDENTIFIER_PATTERN = r"DEMO-APAAR-\d{6}"


class IdentifierFormat(BaseModel):
    pattern: str = Field(min_length=1, max_length=200)
    label: str = Field(min_length=1, max_length=120)
    example: str = Field(max_length=40)

    @field_validator("pattern")
    @classmethod
    def _compiles(cls, value: str) -> str:
        try:
            re.compile(value)
        except re.error as exc:
            raise ValueError(f"Not a valid regular expression: {exc}") from exc
        return value


class IntakePolicy(BaseModel):
    count_statuses: list[str] = Field(min_length=1)


class ConsistencyPolicy(BaseModel):
    min_age_at_admission: int = Field(ge=0, le=100)
    max_age_at_admission: int = Field(ge=1, le=120)
    academic_year_start_month: int = Field(ge=1, le=12)


class PolicySettings(BaseModel):
    identifier_format: IdentifierFormat
    intake_policy: IntakePolicy
    consistency: ConsistencyPolicy
    rules_enabled: dict[str, bool]


DEFAULTS: dict[str, Any] = {
    "identifier_format": {
        "pattern": DEMO_IDENTIFIER_PATTERN,
        "label": "Synthetic demo format: DEMO-APAAR- followed by 6 digits",
        "example": "DEMO-APAAR-000123",
    },
    "intake_policy": {"count_statuses": ["ENROLLED"]},
    "consistency": {
        "min_age_at_admission": 15,
        "max_age_at_admission": 60,
        "academic_year_start_month": 4,
    },
    "rules_enabled": {},
}

IDENTIFIER_PRESETS = [
    {
        "key": "demo",
        "pattern": DEMO_IDENTIFIER_PATTERN,
        "label": "Synthetic demo format: DEMO-APAAR- followed by 6 digits",
        "example": "DEMO-APAAR-000123",
        "note": "Deliberately unlike a real identifier so demo data can never be mistaken for "
        "real APAAR IDs.",
    },
    {
        "key": "numeric12",
        "pattern": r"\d{12}",
        "label": "12-digit numeric (assumed; confirm against the official specification)",
        "example": "",
        "note": "Publicly described APAAR IDs are 12 digits. Format checks never prove an ID is "
        "authentic.",
    },
]


def load_policy(db: Session) -> PolicySettings:
    merged = copy.deepcopy(DEFAULTS)
    for row in db.query(SystemSetting).filter(SystemSetting.key.in_(DEFAULTS.keys())):
        if isinstance(merged[row.key], dict) and isinstance(row.value, dict):
            merged[row.key].update(row.value)
    return PolicySettings.model_validate(merged)


def save_setting(db: Session, key: str, value: dict[str, Any], user_id: Any) -> None:
    if key not in DEFAULTS:
        raise KeyError(key)
    row = db.get(SystemSetting, key)
    if row is None:
        db.add(SystemSetting(key=key, value=value, updated_by_id=user_id))
    else:
        row.value = value
        row.updated_by_id = user_id
        row.updated_at = utcnow()
