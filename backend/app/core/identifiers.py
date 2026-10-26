"""Protection of APAAR-related identifiers.

Three derived values are stored instead of the raw identifier:

* ``fingerprint`` - keyed HMAC-SHA256 of the normalised identifier. Used for uniqueness and
  duplicate matching without storing the identifier in a searchable plain form. A plain hash
  is deliberately NOT used because identifiers are predictable and could be brute-forced.
* ``ciphertext`` - Fernet (AES-128-CBC + HMAC-SHA256) encryption so authorised views such as
  a printed record can recover the identifier.
* ``last4`` - for masked display.

Keys come from the environment. Rotating the HMAC key invalidates existing fingerprints and
needs a re-keying migration; this is documented in docs/security-model.md.
"""

import base64
import hashlib
import hmac
import re
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import get_settings

MASK_CHAR = "•"


def normalize_identifier(raw: str | None) -> str:
    """Trim surrounding/internal whitespace and upper-case. Documented in docs/csv-import.md."""
    if raw is None:
        return ""
    return re.sub(r"\s+", "", raw).upper()


def fingerprint(normalized: str) -> str:
    key = get_settings().identifier_hmac_key.encode("utf-8")
    return hmac.new(key, normalized.encode("utf-8"), hashlib.sha256).hexdigest()


@lru_cache
def _fernet(key: str) -> Fernet:
    """Use the key directly if it is a Fernet key; otherwise derive one from the secret with
    HKDF-SHA256, so a platform-generated random secret of any encoding works."""
    try:
        return Fernet(key.encode("utf-8"))
    except ValueError:
        derived = HKDF(
            algorithm=hashes.SHA256(), length=32, salt=None, info=b"apaar-identifier-encryption"
        ).derive(key.encode("utf-8"))
        return Fernet(base64.urlsafe_b64encode(derived))


def encrypt_identifier(normalized: str) -> str:
    return _fernet(get_settings().identifier_encryption_key).encrypt(normalized.encode()).decode()


def decrypt_identifier(ciphertext: str) -> str | None:
    try:
        return _fernet(get_settings().identifier_encryption_key).decrypt(ciphertext).decode()
    except InvalidToken:
        return None


def last4(normalized: str) -> str:
    return normalized[-4:]


def mask(last_four: str | None) -> str:
    if not last_four:
        return ""
    return MASK_CHAR * 8 + last_four


def matches_format(normalized: str, pattern: str) -> bool:
    try:
        return re.fullmatch(pattern, normalized) is not None
    except re.error:
        return False
