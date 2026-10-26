"""Verification provider boundary.

The application depends only on ``IdentityVerificationProvider``. The only implementation in
this prototype is ``MockApaarProvider``, which is SIMULATED: it never contacts APAAR, AICTE,
DigiLocker or any government system, and its results must always be labelled as simulated.
A real provider can be added only with authorised access, official documentation and
credentials.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.db.base import utcnow

SIMULATED_LABEL = "SIMULATED — NOT OFFICIAL APAAR VERIFICATION"

OUTCOMES = ("match", "no_match", "pending", "unavailable", "error")


@dataclass(frozen=True)
class ProviderResult:
    provider: str
    simulated: bool
    outcome: str
    message: str
    checked_at: datetime


class IdentityVerificationProvider(Protocol):
    name: str
    display_name: str
    simulated: bool

    def verify(self, normalized_identifier: str) -> ProviderResult: ...


class MockApaarProvider:
    """Deterministic simulated outcomes keyed on the identifier's last character, so demos are
    repeatable: 0-6 match, 7 no_match, 8 unavailable, 9 pending, non-digit no_match."""

    name = "mock_apaar"
    display_name = "Mock APAAR provider (simulated)"
    simulated = True

    def verify(self, normalized_identifier: str) -> ProviderResult:
        last = normalized_identifier[-1:] if normalized_identifier else ""
        if last in "0123456":
            outcome, message = "match", "Simulated provider recognises this identifier."
        elif last == "7":
            outcome, message = "no_match", "Simulated provider does not recognise this identifier."
        elif last == "8":
            outcome, message = (
                "unavailable",
                "Simulated provider is unavailable. The record is NOT treated as verified or "
                "invalid; retry later or route to manual review.",
            )
        elif last == "9":
            outcome, message = "pending", "Simulated provider has queued the check for later."
        else:
            outcome, message = "no_match", "Simulated provider does not recognise this identifier."
        return ProviderResult(self.name, True, outcome, f"{SIMULATED_LABEL}. {message}", utcnow())


_PROVIDER = MockApaarProvider()


def get_provider() -> IdentityVerificationProvider:
    return _PROVIDER
