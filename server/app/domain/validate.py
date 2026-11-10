"""GSTIN / place-of-supply / registration validators.

These directly target the TallyPrime import defects the user listed:
  - Invalid GSTIN / GSTIN-UIN not specified / invalid Supplier/Consignee GSTIN
  - Taxability Type invalid or not specified
  - GST Registration Details of the Company invalid or not specified
  - Place of Supply invalid or not specified
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

from .config import STATE_CODES

# 2-digit state + 10-char PAN + 1 entity char + 'Z' (default) + 1 checksum char
GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]$")
PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")

_GST_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def gstin_checksum(gstin14: str) -> str:
    """Compute the 15th GSTIN check character from the first 14 chars."""
    factor = 2
    total = 0
    mod = len(_GST_CHARS)  # 36
    for ch in reversed(gstin14):
        code = _GST_CHARS.index(ch)
        addend = factor * code
        addend = (addend // mod) + (addend % mod)
        total += addend
        factor = 1 if factor == 2 else 2
    check = (mod - (total % mod)) % mod
    return _GST_CHARS[check]


def validate_gstin(gstin: Optional[str]) -> Tuple[bool, str]:
    """Return (is_valid, reason). reason is '' when valid."""
    if not gstin:
        return False, "GSTIN/UIN is not specified"
    g = gstin.strip().upper().replace(" ", "")
    if len(g) != 15:
        return False, f"GSTIN length is {len(g)}, expected 15"
    if not GSTIN_RE.match(g):
        return False, "GSTIN format is invalid"
    if g[:2] not in STATE_CODES:
        return False, f"GSTIN state code '{g[:2]}' is invalid"
    if not PAN_RE.match(g[2:12]):
        return False, "Embedded PAN in GSTIN is invalid"
    if gstin_checksum(g[:14]) != g[14]:
        return False, "GSTIN checksum digit is invalid"
    return True, ""


def state_code_from_gstin(gstin: Optional[str]) -> Optional[str]:
    if gstin and len(gstin) >= 2 and gstin[:2] in STATE_CODES:
        return gstin[:2]
    return None


def validate_place_of_supply(name: str, code: str) -> Tuple[bool, str]:
    if not (name or code):
        return False, "Place of Supply is not specified"
    if code and code not in STATE_CODES:
        return False, f"Place of Supply state code '{code}' is invalid"
    if name and name.lower() not in {v.lower() for v in STATE_CODES.values()}:
        # name might still be a valid variant; only warn if code is also absent
        if not code:
            return False, f"Place of Supply '{name}' is not a recognised state"
    return True, ""
