"""Prototype roles and the permission matrix (mirrored in docs/security-model.md).

These are prototype roles, not official AICTE role definitions. Access is deny-by-default:
a role has only the permissions listed for it here.
"""

from enum import StrEnum


class Role(StrEnum):
    INSTITUTION_OPERATOR = "institution_operator"
    INSTITUTION_ADMIN = "institution_admin"
    CENTRAL_REVIEWER = "central_reviewer"
    AUTHORIZED_VERIFIER = "authorized_verifier"
    SYSTEM_ADMIN = "system_admin"


INSTITUTION_ROLES = frozenset({Role.INSTITUTION_OPERATOR, Role.INSTITUTION_ADMIN})


class Permission(StrEnum):
    STUDENTS_READ = "students.read"
    STUDENTS_WRITE = "students.write"
    UPLOADS_CREATE = "uploads.create"
    UPLOADS_READ = "uploads.read"
    FINDINGS_READ = "findings.read"
    FINDINGS_REVIEW = "findings.review"
    PROGRAMMES_READ = "programmes.read"
    INTAKE_MANAGE = "intake.manage"
    INSTITUTIONS_READ = "institutions.read"
    DASHBOARD_INSTITUTION = "dashboard.institution"
    DASHBOARD_CENTRAL = "dashboard.central"
    REPORTS_EXPORT = "reports.export"
    IDENTITY_CHECK = "verification.identity_check"
    VERIFY_LOOKUP = "verification.lookup"
    CONSENT_MANAGE = "consent.manage"
    RECORDS_ISSUE = "records.issue"
    AUDIT_READ = "audit.read"
    SETTINGS_MANAGE = "settings.manage"


P = Permission

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.INSTITUTION_OPERATOR: frozenset(
        {
            P.STUDENTS_READ,
            P.STUDENTS_WRITE,
            P.UPLOADS_CREATE,
            P.UPLOADS_READ,
            P.FINDINGS_READ,
            P.PROGRAMMES_READ,
            P.DASHBOARD_INSTITUTION,
            P.REPORTS_EXPORT,
            P.IDENTITY_CHECK,
            P.CONSENT_MANAGE,
        }
    ),
    Role.INSTITUTION_ADMIN: frozenset(
        {
            P.STUDENTS_READ,
            P.STUDENTS_WRITE,
            P.UPLOADS_CREATE,
            P.UPLOADS_READ,
            P.FINDINGS_READ,
            P.FINDINGS_REVIEW,
            P.PROGRAMMES_READ,
            P.DASHBOARD_INSTITUTION,
            P.REPORTS_EXPORT,
            P.IDENTITY_CHECK,
            P.CONSENT_MANAGE,
            P.RECORDS_ISSUE,
            P.AUDIT_READ,
        }
    ),
    Role.CENTRAL_REVIEWER: frozenset(
        {
            P.STUDENTS_READ,
            P.UPLOADS_READ,
            P.FINDINGS_READ,
            P.FINDINGS_REVIEW,
            P.PROGRAMMES_READ,
            P.INTAKE_MANAGE,
            P.INSTITUTIONS_READ,
            P.DASHBOARD_CENTRAL,
            P.REPORTS_EXPORT,
            P.IDENTITY_CHECK,
            P.VERIFY_LOOKUP,
            P.AUDIT_READ,
        }
    ),
    Role.AUTHORIZED_VERIFIER: frozenset({P.VERIFY_LOOKUP}),
    Role.SYSTEM_ADMIN: frozenset(
        {
            P.PROGRAMMES_READ,
            P.INTAKE_MANAGE,
            P.INSTITUTIONS_READ,
            P.AUDIT_READ,
            P.SETTINGS_MANAGE,
        }
    ),
}


def has_permission(role: str, permission: Permission) -> bool:
    try:
        return permission in ROLE_PERMISSIONS[Role(role)]
    except ValueError:
        return False


def is_institution_scoped(role: str) -> bool:
    return role in INSTITUTION_ROLES
