"""Runs the rules and reconciles their output with stored findings.

* A condition with an active finding keeps it (evidence is refreshed if it changed).
* A condition a reviewer already closed is not re-raised unless its evidence changed.
* An active finding whose condition is no longer detected is auto-resolved by the system,
  with a review-history entry explaining why.
* Findings of disabled rules are left untouched.
"""

import hashlib
import json
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.models import Finding, Institution, ReviewAction
from app.models.finding import ACTIVE_STATUSES, CLOSED_STATUSES
from app.services.settings import PolicySettings, load_policy
from app.services.validation.rules import (
    RULES,
    RULES_BY_CODE,
    FindingDraft,
    evaluate_cross_institution,
    load_context,
)


@dataclass
class ReconcileStats:
    opened: int = 0
    opened_by_institution: dict[uuid.UUID, int] = field(default_factory=dict)
    refreshed: int = 0
    unchanged: int = 0
    auto_resolved: int = 0
    suppressed: int = 0


def evidence_signature(draft: FindingDraft) -> str:
    payload = json.dumps(
        {"e": draft.evidence, "r": draft.restricted_evidence}, sort_keys=True, default=str
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def enabled_rule_codes(policy: PolicySettings) -> set[str]:
    return {r.code for r in RULES if policy.rules_enabled.get(r.code, True)}


def run_validation(
    db: Session,
    institution_ids: Iterable[uuid.UUID],
    *,
    batch_id: uuid.UUID | None = None,
    batch_institution_id: uuid.UUID | None = None,
    policy: PolicySettings | None = None,
) -> ReconcileStats:
    """Re-run every enabled rule for ``institution_ids`` (plus the global cross-institution
    rule). ``batch_id`` is recorded as the source only on findings of the batch's own
    institution, so a finding never points at another institution's upload."""
    policy = policy or load_policy(db)
    enabled = enabled_rule_codes(policy)
    institution_ids = list(dict.fromkeys(institution_ids))
    local_codes = [r.code for r in RULES if r.scope == "institution" and r.code in enabled]
    global_codes = [r.code for r in RULES if r.scope == "global" and r.code in enabled]

    drafts: dict[str, FindingDraft] = {}
    for institution in db.scalars(select(Institution).where(Institution.id.in_(institution_ids))):
        ctx = load_context(db, institution, policy)
        for code in local_codes:
            evaluate = RULES_BY_CODE[code].evaluate
            assert evaluate is not None
            for draft in evaluate(ctx):
                drafts[draft.dedupe_key] = draft
    if "CROSS_INSTITUTION_DUPLICATE" in global_codes:
        for draft in evaluate_cross_institution(db, policy):
            drafts[draft.dedupe_key] = draft

    scope_filters = []
    if local_codes and institution_ids:
        scope_filters.append(
            and_(Finding.institution_id.in_(institution_ids), Finding.rule_code.in_(local_codes))
        )
    if global_codes:
        scope_filters.append(Finding.rule_code.in_(global_codes))
    active: dict[str, Finding] = {}
    if scope_filters:
        active = {
            f.dedupe_key: f
            for f in db.scalars(
                select(Finding)
                .where(Finding.status.in_(ACTIVE_STATUSES))
                .where(or_(*scope_filters))
            )
        }

    closed: set[tuple[str, str]] = set()
    keys = list(drafts)
    for start in range(0, len(keys), 500):
        chunk = keys[start : start + 500]
        closed.update(
            db.execute(
                select(Finding.dedupe_key, Finding.evidence_signature)
                .where(Finding.dedupe_key.in_(chunk))
                .where(Finding.status.in_(CLOSED_STATUSES))
            )
        )

    stats = ReconcileStats()
    now = utcnow()
    for key, draft in drafts.items():
        signature = evidence_signature(draft)
        existing = active.get(key)
        if existing is not None:
            if existing.evidence_signature != signature:
                existing.evidence = draft.evidence
                existing.restricted_evidence = draft.restricted_evidence
                existing.reason = draft.reason
                existing.evidence_signature = signature
                db.add(
                    ReviewAction(
                        finding_id=existing.id,
                        action="evidence_updated",
                        comment="Evidence refreshed on re-validation",
                    )
                )
                stats.refreshed += 1
            else:
                stats.unchanged += 1
            continue
        if (key, signature) in closed:
            stats.suppressed += 1
            continue
        spec = RULES_BY_CODE[draft.rule_code]
        finding = Finding(
            id=uuid.uuid4(),
            institution_id=draft.institution_id,
            rule_code=draft.rule_code,
            category=spec.category,
            severity=spec.severity,
            status="open",
            title=spec.title,
            reason=draft.reason,
            evidence=draft.evidence,
            restricted_evidence=draft.restricted_evidence,
            recommended_action=spec.recommended_action,
            dedupe_key=key,
            evidence_signature=signature,
            target_type=draft.target_type,
            student_id=draft.student_id,
            admission_id=draft.admission_id,
            programme_id=draft.programme_id,
            academic_year=draft.academic_year,
            source_batch_id=batch_id if draft.institution_id == batch_institution_id else None,
        )
        db.add(finding)
        db.add(
            ReviewAction(
                finding_id=finding.id,
                action="created",
                to_status="open",
                comment=f"Raised automatically by rule {draft.rule_code}",
            )
        )
        stats.opened += 1
        stats.opened_by_institution[draft.institution_id] = (
            stats.opened_by_institution.get(draft.institution_id, 0) + 1
        )

    for key, finding in active.items():
        if key in drafts:
            continue
        db.add(
            ReviewAction(
                finding_id=finding.id,
                action="auto_resolved",
                from_status=finding.status,
                to_status="resolved",
                comment="Condition no longer detected on re-validation",
            )
        )
        finding.status = "resolved"
        finding.resolved_at = now
        finding.resolved_by_id = None
        stats.auto_resolved += 1

    db.flush()
    return stats
